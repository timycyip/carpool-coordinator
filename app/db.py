"""DynamoDB client factory dependency.

Centralizes the boto3 DynamoDB client used by repositories and the
audit middleware. The default ``get_ddb_client`` dependency reads the
region from ``AWS_REGION`` (falling back to ``us-east-2`` per ADR-0003)
and returns a low-level client compatible with ``DynamoRepository``.

Tests override this dependency (e.g. by setting ``app.state.ddb_client``
or using FastAPI's ``app.dependency_overrides``) to inject a moto-mocked
client without touching real AWS.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


_DEFAULT_REGION = "us-east-2"


def get_ddb_client() -> DynamoDBClient:
    """FastAPI dependency yielding a low-level boto3 DynamoDB client."""
    region = os.environ.get("AWS_REGION", _DEFAULT_REGION)
    return boto3.client("dynamodb", region_name=region)
