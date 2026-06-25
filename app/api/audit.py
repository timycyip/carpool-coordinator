"""Audit log read API.

Implements ``GET /audit`` (API contracts §3.16). Returns a cursor-paginated
list of :class:`~app.models.audit.AuditEvent` records.

Filters supported: ``from`` / ``to`` (UTC ISO-8601 dates, inclusive),
``event_type``, ``session_code``. Pagination via opaque ``cursor`` (the
last ``SK`` of the previous page) and ``limit`` (default 50, max 100).

Access is restricted to Superuser and Manager via RBAC (require_role).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from app.db import get_ddb_client
from app.middleware.rbac import require_role
from app.models.audit import AuditEvent, PaginatedResponse
from app.models.auth import TokenPayload
from app.models.roles import Role
from app.repositories.audit import AuditRepository

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


router = APIRouter(prefix="/audit", tags=["audit"])

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601 date (YYYY-MM-DD): {exc}") from exc


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _event_from_item(item: dict[str, Any]) -> AuditEvent:
    ts_raw = item.get("timestamp")
    if isinstance(ts_raw, datetime):
        timestamp = ts_raw
    elif isinstance(ts_raw, str):
        timestamp = datetime.fromisoformat(ts_raw)
    else:
        timestamp = datetime.now(tz=timezone.utc)
    details = item.get("details") or {}
    return AuditEvent(
        event_id=item.get("event_id", ""),
        timestamp=timestamp,
        actor_sub=item.get("actor_sub"),
        event_type=item.get("event_type", ""),
        session_code=item.get("session_code"),
        ip_address=item.get("ip_address"),
        details=details if isinstance(details, dict) else {},
    )


def _build_filters(
    event_type: str | None, session_code: str | None
) -> dict[str, Any] | None:
    filters: dict[str, Any] = {}
    if event_type:
        filters["event_type"] = event_type
    if session_code:
        filters["session_code"] = session_code
    return filters or None


def _iter_dates(start: date, end: date) -> list[date]:
    if end < start:
        return []
    days: list[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


@router.get("", response_model=PaginatedResponse[AuditEvent])
async def list_audit_events(
    _user: TokenPayload = Depends(require_role(Role.MANAGER, Role.SUPERUSER)),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    session_code: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    client: DynamoDBClient = Depends(get_ddb_client),
) -> PaginatedResponse[AuditEvent]:
    """Return paginated audit events (Superuser or Manager only).

    Query params ``from`` and ``to`` are ISO-8601 dates (``YYYY-MM-DD``,
    UTC). If omitted, ``to`` defaults to today and ``from`` defaults to
    ``to`` (single day). ``cursor`` is the opaque ``SK`` returned in the
    previous page's ``next_cursor``; omit it on the first page.
    """
    today = datetime.now(tz=timezone.utc).date()
    start_date = _parse_date(from_, "from") if from_ else today
    end_date = _parse_date(to, "to") if to else start_date

    repo = AuditRepository(table_name="app_data", client=client)
    filters = _build_filters(event_type, session_code)

    items: list[AuditEvent] = []
    next_cursor: str | None = None
    skipped_cursor = cursor is None
    last_sk: str | None = None

    for d in _iter_dates(start_date, end_date):
        date_str = d.isoformat()
        raw_items = await repo.query_audit(date_str, filters=filters)
        for raw in raw_items:
            sk = raw.get("SK", "")
            if not skipped_cursor:
                if sk == cursor:
                    skipped_cursor = True
                continue
            items.append(_event_from_item(raw))
            last_sk = sk
            if len(items) >= limit:
                index_in_day = raw_items.index(raw)
                if index_in_day + 1 < len(raw_items):
                    next_cursor = last_sk
                break
        if len(items) >= limit:
            break

    return PaginatedResponse[AuditEvent](
        items=items[:limit],
        next_cursor=next_cursor,
        limit=limit,
    )


__all__ = ["router", "_to_iso", "_iter_dates", "_parse_date"]
