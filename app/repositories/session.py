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

    async def delete_session_records(self, code: str) -> None:
        """Delete every item in a session partition, including all query pages."""
        last_key: dict[str, Any] | None = None
        while True:
            kwargs: dict[str, Any] = {
                "TableName": self.table_name,
                "KeyConditionExpression": "PK = :pk",
                "ExpressionAttributeValues": {
                    ":pk": self._serializer.serialize(f"SESSION#{code}")
                },
            }
            if last_key is not None:
                kwargs["ExclusiveStartKey"] = last_key
            response = self.client.query(**kwargs)
            for raw_item in response.get("Items", []):
                item = self._from_dynamo(raw_item)
                await self.delete_item({"PK": item["PK"], "SK": item["SK"]})
            last_key = response.get("LastEvaluatedKey")
            if last_key is None:
                return
