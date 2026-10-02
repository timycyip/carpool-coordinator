"""Runtime resolution of Terraform-provided DynamoDB table names."""

from __future__ import annotations

from typing import Any

import pytest

from app.config import get_table_name
from app.middleware.audit import AuditLogger
from app.middleware.rate_limit import RateLimiter


@pytest.mark.parametrize(
    ("environment_variable", "default"),
    [
        ("APP_DATA_TABLE_NAME", "app_data"),
        ("RATE_LIMIT_CACHE_TABLE_NAME", "rate_limit_cache"),
        ("BRUTE_FORCE_COUNTER_TABLE_NAME", "brute_force_counter"),
        ("GEOCODE_CACHE_TABLE_NAME", "geocode_cache"),
        ("SESSION_CACHE_TABLE_NAME", "session_cache"),
    ],
)
def test_table_name_uses_environment_and_preserves_default(
    monkeypatch: pytest.MonkeyPatch,
    environment_variable: str,
    default: str,
) -> None:
    monkeypatch.delenv(environment_variable, raising=False)
    assert get_table_name(environment_variable, default) == default

    configured_name = f"configured-{default}"
    monkeypatch.setenv(environment_variable, configured_name)
    assert get_table_name(environment_variable, default) == configured_name


def test_empty_table_name_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DATA_TABLE_NAME", "")

    assert get_table_name("APP_DATA_TABLE_NAME", "app_data") == "app_data"


def test_audit_logger_reads_app_data_table_at_construction(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    monkeypatch.setenv("APP_DATA_TABLE_NAME", "configured-app-data")

    logger = AuditLogger(client=ddb_client)

    assert logger._repo.table_name == "configured-app-data"


def test_rate_limiter_reads_cache_table_at_construction(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    monkeypatch.setenv("RATE_LIMIT_CACHE_TABLE_NAME", "configured-rate-limit")

    limiter = RateLimiter(client=ddb_client)

    assert limiter._table == "configured-rate-limit"


@pytest.mark.asyncio
async def test_rbac_reads_app_data_table_at_request_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.middleware.rbac import _lookup_session_roles
    from app.models.auth import TokenPayload

    class RecordingClient:
        def __init__(self) -> None:
            self.table_names: list[str] = []

        def get_item(self, *, TableName: str, Key: dict[str, Any]) -> dict[str, Any]:
            self.table_names.append(TableName)
            return {}

    client = RecordingClient()
    user = TokenPayload(
        sub="user-123",
        email="u@example.com",
        name="User",
        global_role="none",
        exp=2_000_000_000,
    )
    monkeypatch.setenv("APP_DATA_TABLE_NAME", "configured-app-data")

    await _lookup_session_roles(user, "ABC123", client)  # type: ignore[arg-type]

    assert client.table_names == ["configured-app-data", "configured-app-data"]
