"""User repository — USER#<sub> / METADATA in app_data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories.base import DynamoRepository


class UserRepository(DynamoRepository):
    async def get_by_sub(self, sub: str) -> dict[str, Any] | None:
        return await self.get_item({"PK": f"USER#{sub}", "SK": "METADATA"})

    async def upsert(self, sub: str, email: str, name: str) -> dict[str, Any]:
        """Create or update a user, preserving global_roles and original created_at.

        Uses UpdateItem with ``if_not_exists`` so that ``created_at`` and
        ``global_roles`` are only set on first creation and never overwritten
        by subsequent logins.
        """
        now = datetime.now(timezone.utc).isoformat()
        key = {"PK": f"USER#{sub}", "SK": "METADATA"}
        update_expr = (
            "SET email = :email, #name = :name, "
            "created_at = if_not_exists(created_at, :now), "
            "global_roles = if_not_exists(global_roles, :empty_list)"
        )
        expr_values: dict[str, Any] = {
            ":email": email,
            ":name": name,
            ":now": now,
            ":empty_list": [],
        }
        expr_names: dict[str, str] = {"#name": "name"}
        await self.update_item(
            key=key,
            update_expression=update_expr,
            expr_values=expr_values,
            expr_names=expr_names,
        )
        result = await self.get_by_sub(sub)
        return result  # type: ignore[return-value]
