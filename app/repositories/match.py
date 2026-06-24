"""Match repository — SESSION#<code> / MATCH#V<n> in app_data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.base import DynamoRepository

_RESERVED_KEYS = frozenset({"PK", "SK", "version"})


def _match_sk(version: int) -> str:
    """Return the SK for a match version (zero-padded to 4 digits).

    Raises ``ValueError`` if version < 1.
    """
    if version < 1:
        raise ValueError(f"Match version must be >= 1, got {version}")
    return f"MATCH#V{version:04d}"


class MatchRepository(DynamoRepository):
    async def create(
        self, session_code: str, version: int, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        safe_attrs = {k: v for k, v in attrs.items() if k not in _RESERVED_KEYS}
        item: dict[str, Any] = {
            **safe_attrs,
            "PK": f"SESSION#{session_code}",
            "SK": _match_sk(version),
            "version": version,
        }
        await self.put_item(item, condition_expression="attribute_not_exists(PK)")
        return item

    async def get_latest(self, session_code: str) -> dict[str, Any] | None:
        # Advisory A7 (Phase 1 review): The ERD §3.3 defines a
        # gsi_latest_match_by_session GSI, but it is architecturally redundant.
        # A main-table Query on PK = SESSION#<code> with SK begins_with MATCH#,
        # ScanIndexForward=False, Limit=1 returns the highest-version match at
        # identical cost (single Query, same partition). The GSI is therefore
        # NOT provisioned in Terraform — this main-table Query suffices.
        results = await self._query_match_versions(
            session_code, descending=True, limit=1
        )
        return results[0] if results else None

    async def list_versions(self, session_code: str) -> list[dict[str, Any]]:
        return await self._query_match_versions(session_code)

    async def update_status(
        self,
        session_code: str,
        version: int,
        status: str,
        approved_by: str | None,
    ) -> None:
        if status == "approved":
            if approved_by is None:
                raise ValueError(
                    "approved_by is required when setting status to 'approved'"
                )
            now = datetime.now(timezone.utc).isoformat()
            update_expr = (
                "SET #status = :status, "
                "approved_at = :approved_at, "
                "approved_by = :approved_by"
            )
            expr_values: dict[str, Any] = {
                ":status": status,
                ":approved_at": now,
                ":approved_by": approved_by,
            }
        else:
            update_expr = "SET #status = :status REMOVE approved_at, approved_by"
            expr_values = {":status": status}

        expr_names: dict[str, str] = {"#status": "status"}
        await self.update_item(
            key={"PK": f"SESSION#{session_code}", "SK": _match_sk(version)},
            update_expression=update_expr,
            expr_values=expr_values,
            expr_names=expr_names,
        )

    async def _query_match_versions(
        self,
        session_code: str,
        *,
        descending: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.query(
            key_condition="PK = :pk AND begins_with(SK, :sk)",
            expr_values={":pk": f"SESSION#{session_code}", ":sk": "MATCH#"},
            scan_index_forward=not descending,
            limit=limit,
        )
