"""Session management logic backed by the ERD session item."""

from __future__ import annotations

import secrets
import string
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.models.auth import TokenPayload
from app.models.session import (
    AnchorLocation,
    SessionCreate,
    SessionResponse,
    SessionStatus,
    SessionUpdate,
)
from app.repositories.session import SessionRepository

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_ALLOWED_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.DRAFT: {SessionStatus.REGISTRATION_OPEN, SessionStatus.CLOSED},
    SessionStatus.REGISTRATION_OPEN: {
        SessionStatus.MATCHING_PENDING,
        SessionStatus.CLOSED,
    },
    SessionStatus.MATCHING_PENDING: {
        SessionStatus.MATCHING_PROPOSED,
        SessionStatus.CLOSED,
    },
    SessionStatus.MATCHING_PROPOSED: {SessionStatus.APPROVED, SessionStatus.CLOSED},
    SessionStatus.APPROVED: {SessionStatus.CLOSED},
    SessionStatus.CLOSED: set(),
}


def _not_found(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "SESSION_CODE_NOT_FOUND",
                "message": "No session matches this code.",
                "details": {"session_code": code},
            }
        },
    )


def _session_response(item: dict[str, Any], *, admin: bool) -> SessionResponse:
    values = {
        "session_code": item.get("code", item["PK"].removeprefix("SESSION#")),
        "title": item["title"],
        "description": item.get("description"),
        "trip_mode": item["trip_mode"],
        "anchor_location": item["anchor_location"],
        "earliest_pickup": item["earliest_pickup"],
        "latest_arrival": item["latest_arrival"],
        "registration_deadline": item["registration_deadline"],
        "status": item["status"],
        "created_by_sub": item.get("created_by_sub", item.get("created_by", "")),
        "created_at": item["created_at"],
        "updated_at": item.get("updated_at", item["created_at"]),
    }
    if admin and "capacity_hint" in item:
        values["capacity_hint"] = item["capacity_hint"]
    return SessionResponse.model_validate(values)


def _as_datetime(value: datetime | str) -> datetime:
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def _geocoding_unavailable() -> HTTPException:
    """Fail closed until the Phase 3 cached Nominatim service is available."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Session anchor geocoding is unavailable.",
            }
        },
    )


class SessionService:
    """Apply session invariants and map ERD records to API models."""

    def __init__(
        self,
        repository: SessionRepository,
        geocoder: Callable[[str], Awaitable[AnchorLocation]] | None = None,
    ) -> None:
        self.repository = repository
        self.geocoder = geocoder

    async def _geocode_anchor(self, postal_code: str) -> AnchorLocation:
        if self.geocoder is None:
            raise _geocoding_unavailable()
        return await self.geocoder(postal_code)

    @staticmethod
    def _generate_code() -> str:
        return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))

    @staticmethod
    def _is_global_admin(actor: TokenPayload) -> bool:
        return actor.global_role in {"superuser", "manager"}

    async def _is_session_admin(self, code: str, actor: TokenPayload) -> bool:
        if self._is_global_admin(actor):
            return True
        assignment = await self.repository.get_item(
            {"PK": f"SESSION#{code}", "SK": f"ADMIN#{actor.sub}"}
        )
        return assignment is not None

    async def create(self, body: SessionCreate, actor: TokenPayload) -> SessionResponse:
        """Persist a session only after resolving its anchor to real coordinates."""
        anchor = await self._geocode_anchor(body.anchor_postal_code)
        now = datetime.now(timezone.utc).isoformat()
        attrs: dict[str, Any] = {
            "title": body.title,
            "description": body.description,
            "trip_mode": body.trip_mode.value,
            "anchor_location": anchor.model_dump(mode="json"),
            "earliest_pickup": body.earliest_pickup.isoformat(),
            "latest_arrival": body.latest_arrival.isoformat(),
            "registration_deadline": body.registration_deadline.isoformat(),
            "status": SessionStatus.DRAFT.value,
            "created_by": actor.sub,
            "created_at": now,
            "updated_at": now,
        }
        if body.capacity_hint is not None:
            attrs["capacity_hint"] = body.capacity_hint

        for _ in range(3):
            code = self._generate_code()
            attrs["code"] = code
            try:
                item = await self.repository.create(code, attrs)
                return _session_response(item, admin=True)
            except ClientError as exc:
                if (
                    exc.response.get("Error", {}).get("Code")
                    != "ConditionalCheckFailedException"
                ):
                    raise

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SESSION_ALREADY_EXISTS",
                    "message": "A unique session code could not be generated.",
                }
            },
        )

    async def get(self, code: str, actor: TokenPayload) -> SessionResponse:
        normalized_code = code.upper()
        item = await self.repository.get_by_code(normalized_code)
        if item is None:
            raise _not_found(normalized_code)
        return _session_response(
            item,
            admin=await self._is_session_admin(normalized_code, actor),
        )

    async def update(
        self, code: str, body: SessionUpdate, actor: TokenPayload
    ) -> SessionResponse:
        normalized_code = code.upper()
        item = await self.repository.get_by_code(normalized_code)
        if item is None:
            raise _not_found(normalized_code)

        changes = body.model_dump(exclude_unset=True)
        if "status" in changes and changes["status"] is not None:
            current = SessionStatus(item["status"])
            new_status = SessionStatus(changes["status"])
            self._validate_transition(current, new_status)
            changes["status"] = new_status.value

        next_earliest = _as_datetime(
            changes.get("earliest_pickup", item["earliest_pickup"])
        )
        next_latest = _as_datetime(
            changes.get("latest_arrival", item["latest_arrival"])
        )
        next_deadline = _as_datetime(
            changes.get("registration_deadline", item["registration_deadline"])
        )
        if next_latest < next_earliest:
            raise self._invalid_time_window(
                "latest_arrival must be at or after earliest_pickup"
            )
        if next_deadline > next_earliest:
            raise self._invalid_time_window(
                "registration_deadline must be at or before earliest_pickup"
            )

        postal_code = changes.pop("anchor_postal_code", None)
        if postal_code is not None:
            anchor = await self._geocode_anchor(postal_code)
            changes["anchor_location"] = anchor.model_dump(mode="json")
        for field in (
            "earliest_pickup",
            "latest_arrival",
            "registration_deadline",
        ):
            if field in changes and isinstance(changes[field], datetime):
                changes[field] = changes[field].isoformat()
        if changes:
            changes["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self.repository.update(normalized_code, changes)

        updated = await self.repository.get_by_code(normalized_code)
        if updated is None:
            raise _not_found(normalized_code)
        return _session_response(
            updated,
            admin=await self._is_session_admin(normalized_code, actor),
        )

    async def delete(self, code: str, actor: TokenPayload) -> None:
        del actor  # Authorization is enforced by the route's Superuser dependency.
        normalized_code = code.upper()
        item = await self.repository.get_by_code(normalized_code)
        if item is None:
            raise _not_found(normalized_code)

        await self.repository.delete_session_records(normalized_code)

    @staticmethod
    def _validate_transition(
        current: SessionStatus, new: SessionStatus
    ) -> None:
        if current == new:
            return
        if new not in _ALLOWED_TRANSITIONS[current]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SESSION_NOT_OPEN",
                        "message": "The requested session status transition is not allowed.",
                        "details": {
                            "current_status": current.value,
                            "requested_status": new.value,
                        },
                    }
                },
            )

    @staticmethod
    def _invalid_time_window(message: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                }
            },
        )


__all__ = ["SessionService"]
