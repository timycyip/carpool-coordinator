"""Registration repository — SESSION#<code> / REG#<sub> in app_data.

On create, populates ``gsi1_pk`` / ``gsi1_sk`` so the registration is
reachable via the ``gsi_sessions_by_user`` GSI (ERD §3.2).
"""

from __future__ import annotations

from typing import Any

from app.repositories.base import DynamoRepository

_RESERVED_KEYS = frozenset({"PK", "SK", "gsi1_pk", "gsi1_sk", "gsi2_pk", "gsi2_sk"})


class RegistrationRepository(DynamoRepository):
    async def create(
        self, session_code: str, sub: str, attrs: dict[str, Any]
    ) -> dict[str, Any]:
        safe_attrs = {k: v for k, v in attrs.items() if k not in _RESERVED_KEYS}
        item: dict[str, Any] = {
            **safe_attrs,
            "PK": f"SESSION#{session_code}",
            "SK": f"REG#{sub}",
            "gsi1_pk": f"USER#{sub}",
            "gsi1_sk": f"SESSION#{session_code}",
        }
        await self.put_item(item, condition_expression="attribute_not_exists(PK)")
        return item

    async def get(self, session_code: str, sub: str) -> dict[str, Any] | None:
        return await self.get_item(
            {"PK": f"SESSION#{session_code}", "SK": f"REG#{sub}"}
        )

    async def list_by_session(self, session_code: str) -> list[dict[str, Any]]:
        return await self.query(
            key_condition="PK = :pk AND begins_with(SK, :sk)",
            expr_values={":pk": f"SESSION#{session_code}", ":sk": "REG#"},
        )

    async def update(self, session_code: str, sub: str, attrs: dict[str, Any]) -> None:
        if not attrs:
            return
        update_expr, expr_names, expr_values = self.build_update_expression(attrs)
        await self.update_item(
            key={"PK": f"SESSION#{session_code}", "SK": f"REG#{sub}"},
            update_expression=update_expr,
            expr_values=expr_values,
            expr_names=expr_names,
        )

    async def delete(self, session_code: str, sub: str) -> None:
        await self.delete_item({"PK": f"SESSION#{session_code}", "SK": f"REG#{sub}"})
