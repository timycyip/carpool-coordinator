"""Base DynamoDB repository with typed helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import boto3.dynamodb.types as dynamo_types

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


class DynamoRepository:
    """Base class wrapping the low-level boto3 DynamoDB client.

    Accepts and returns plain Python dicts; DynamoDB JSON serialization
    is handled internally via ``TypeSerializer`` / ``TypeDeserializer``.
    """

    def __init__(self, table_name: str, client: DynamoDBClient) -> None:
        self.table_name = table_name
        self.client = client
        self._serializer = dynamo_types.TypeSerializer()
        self._deserializer = dynamo_types.TypeDeserializer()

    def _to_dynamo(self, item: dict[str, Any]) -> dict[str, Any]:
        return {k: self._serializer.serialize(v) for k, v in item.items()}

    def _from_dynamo(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            k: self._convert(self._deserializer.deserialize(v)) for k, v in item.items()
        }

    @staticmethod
    def _convert(value: Any) -> Any:
        if isinstance(value, Decimal):
            return int(value) if value % 1 == 0 else float(value)
        if isinstance(value, list):
            return [DynamoRepository._convert(v) for v in value]
        if isinstance(value, dict):
            return {k: DynamoRepository._convert(v) for k, v in value.items()}
        return value

    async def put_item(
        self,
        item: dict[str, Any],
        condition_expression: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "TableName": self.table_name,
            "Item": self._to_dynamo(item),
        }
        if condition_expression is not None:
            kwargs["ConditionExpression"] = condition_expression
        self.client.put_item(**kwargs)

    async def get_item(self, key: dict[str, Any]) -> dict[str, Any] | None:
        resp = self.client.get_item(TableName=self.table_name, Key=self._to_dynamo(key))
        raw = resp.get("Item")
        if raw is None:
            return None
        return self._from_dynamo(raw)

    async def query(
        self,
        key_condition: str,
        expr_names: dict[str, str] | None = None,
        expr_values: dict[str, Any] | None = None,
        filter_expression: str | None = None,
        scan_index_forward: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "TableName": self.table_name,
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_index_forward,
        }
        if expr_names:
            kwargs["ExpressionAttributeNames"] = expr_names
        if expr_values:
            kwargs["ExpressionAttributeValues"] = {
                k: self._serializer.serialize(v) for k, v in expr_values.items()
            }
        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression
        if limit is not None:
            kwargs["Limit"] = limit
        resp = self.client.query(**kwargs)
        return [self._from_dynamo(item) for item in resp.get("Items", [])]

    async def update_item(
        self,
        key: dict[str, Any],
        update_expression: str,
        expr_values: dict[str, Any],
        expr_names: dict[str, str] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "TableName": self.table_name,
            "Key": self._to_dynamo(key),
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": {
                k: self._serializer.serialize(v) for k, v in expr_values.items()
            },
        }
        if expr_names:
            kwargs["ExpressionAttributeNames"] = expr_names
        self.client.update_item(**kwargs)

    async def delete_item(self, key: dict[str, Any]) -> None:
        self.client.delete_item(TableName=self.table_name, Key=self._to_dynamo(key))

    @staticmethod
    def build_update_expression(
        attrs: dict[str, Any],
        name_prefix: str = "a",
        value_prefix: str = "v",
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Build a SET update expression from a dict of attribute name→value.

        Returns (update_expression, expression_attribute_names, expression_attribute_values).
        """
        parts: list[str] = []
        expr_names: dict[str, str] = {}
        expr_values: dict[str, Any] = {}
        for i, (k, v) in enumerate(attrs.items()):
            name_key = f"#{name_prefix}{i}"
            value_key = f":{value_prefix}{i}"
            parts.append(f"{name_key} = {value_key}")
            expr_names[name_key] = k
            expr_values[value_key] = v
        return "SET " + ", ".join(parts), expr_names, expr_values
