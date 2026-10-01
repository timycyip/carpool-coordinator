"""Session repository — SESSION#<code> / METADATA in app_data."""

from __future__ import annotations

from typing import Any

from app.repositories.base import DynamoRepository

_RESERVED_KEYS = frozenset({"PK", "SK"})


class SessionRepository(DynamoRepository):
    async def create(self, code: str, attrs: dict[str, Any]) -> dict[str, Any]:
        safe_attrs = {k: v for k, v in attrs.items() if k not in _RESERVED_KEYS}
        item: dict[str, Any] = {
            **safe_attrs,
            "PK": f"SESSION#{code}",
            "SK": "METADATA",
        }
        await self.put_item(item, condition_expression="attribute_not_exists(PK)")
        return item

    async def get_by_code(self, code: str) -> dict[str, Any] | None:
        return await self.get_item({"PK": f"SESSION#{code}", "SK": "METADATA"})

    async def update(self, code: str, attrs: dict[str, Any]) -> None:
        if not attrs:
            return
        update_expr, expr_names, expr_values = self.build_update_expression(attrs)
        await self.update_item(
            key={"PK": f"SESSION#{code}", "SK": "METADATA"},
            update_expression=update_expr,
            expr_values=expr_values,
            expr_names=expr_names,
        )

    async def delete(self, code: str) -> None:
        await self.delete_item({"PK": f"SESSION#{code}", "SK": "METADATA"})
