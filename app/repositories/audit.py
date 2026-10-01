"""Audit repository — AUDIT#<YYYY-MM-DD> / <ISO-ts>#<event_id> in app_data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.base import DynamoRepository

_RESERVED_KEYS = frozenset({"PK", "SK"})


class AuditRepository(DynamoRepository):
    async def write(self, date_str: str, event_id: str, attrs: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        safe_attrs = {k: v for k, v in attrs.items() if k not in _RESERVED_KEYS}
        item: dict[str, Any] = {
            **safe_attrs,
            "PK": f"AUDIT#{date_str}",
            "SK": f"{now}#{event_id}",
        }
        await self.put_item(item, condition_expression="attribute_not_exists(PK)")

    async def query_audit(
        self,
        date_str: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        expr_values: dict[str, Any] = {":pk": f"AUDIT#{date_str}"}
        key_condition = "PK = :pk"

        if from_ts and to_ts:
            key_condition += " AND SK BETWEEN :from AND :to"
            expr_values[":from"] = from_ts
            expr_values[":to"] = to_ts
        elif from_ts:
            key_condition += " AND SK >= :from"
            expr_values[":from"] = from_ts
        elif to_ts:
            key_condition += " AND SK <= :to"
            expr_values[":to"] = to_ts

        filter_expr: str | None = None
        expr_names: dict[str, str] | None = None
        if filters:
            parts: list[str] = []
            expr_names = {}
            for i, (k, v) in enumerate(filters.items()):
                name_key = f"#f{i}"
                value_key = f":f{i}"
                parts.append(f"{name_key} = {value_key}")
                expr_names[name_key] = k
                expr_values[value_key] = v
            filter_expr = " AND ".join(parts)

        return await super().query(
            key_condition=key_condition,
            expr_values=expr_values,
            expr_names=expr_names,
            filter_expression=filter_expr,
        )
