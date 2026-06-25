"""AuditLogger middleware tests.

Covers FR-11 acceptance criteria for the middleware layer:
  - PK/SK pattern (AUDIT#<YYYY-MM-DD> / <ISO-ts>#<UUID>) per ERD §2.6
  - daily partitioning
  - uniqueness of event_id
  - fire-and-forget write semantics (a DB failure does not propagate)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.middleware.audit import (
    EVENT_AUTH_LOGIN_SUCCESS,
    AuditLogger,
)


def _make_request(
    headers: dict[str, str] | None = None, client_host: str = "1.2.3.4"
) -> Request:
    """Build a minimal Starlette Request with controllable IP/headers."""
    headers = headers or {}
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": (client_host, 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


@pytest.fixture()
def audit_logger(ddb_client: Any) -> AuditLogger:
    return AuditLogger(client=ddb_client, table_name="app_data")


@pytest.mark.asyncio
async def test_log_writes_item_with_correct_pk_sk(
    audit_logger: AuditLogger,
    ddb_client: Any,
) -> None:
    request = _make_request()
    await audit_logger.log(
        EVENT_AUTH_LOGIN_SUCCESS,
        actor_sub="user-123",
        session_code=None,
        details={"method": "google"},
        request=request,
    )
    await audit_logger.drain()

    resp = ddb_client.scan(TableName="app_data")
    items = resp.get("Items", [])
    assert len(items) == 1
    item = {k: list(v.values())[0] for k, v in items[0].items()}

    pk = item["PK"]
    assert pk.startswith("AUDIT#")
    assert len(pk) == len("AUDIT#") + 10  # YYYY-MM-DD suffix

    sk = item["SK"]
    assert "#" in sk
    assert item["event_type"] == EVENT_AUTH_LOGIN_SUCCESS
    assert item["actor_sub"] == "user-123"


@pytest.mark.asyncio
async def test_two_events_same_day_share_partition(
    audit_logger: AuditLogger,
    ddb_client: Any,
) -> None:
    request = _make_request()
    await audit_logger.log(
        "session.created",
        actor_sub="user-1",
        session_code="ABC123",
        details={},
        request=request,
    )
    await audit_logger.log(
        "session.updated",
        actor_sub="user-1",
        session_code="ABC123",
        details={},
        request=request,
    )
    await audit_logger.drain()

    resp = ddb_client.scan(TableName="app_data")
    items = resp.get("Items", [])
    assert len(items) == 2
    pks = {_flatten(item["PK"]) for item in items}
    assert len(pks) == 1  # both events share the same partition


@pytest.mark.asyncio
async def test_events_on_different_days_have_different_pks(
    audit_logger: AuditLogger,
    ddb_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two events with timestamps on different UTC dates must land in
    distinct ``AUDIT#<date>`` partitions."""

    request = _make_request()
    dates = ["2026-06-23", "2026-06-24"]
    counter = {"i": 0}

    def fake_now(_cls: type[Any]) -> Any:
        from datetime import datetime, timezone

        d = dates[counter["i"]]
        counter["i"] += 1
        return datetime.fromisoformat(f"{d}T12:00:00+00:00").astimezone(timezone.utc)

    from app.middleware import audit as audit_mod

    monkeypatch.setattr(audit_mod, "datetime", MagicMock(now=fake_now))

    await audit_logger.log(
        "evt-a", actor_sub="u", session_code=None, details={}, request=request
    )
    await audit_logger.log(
        "evt-b", actor_sub="u", session_code=None, details={}, request=request
    )
    await audit_logger.drain()

    resp = ddb_client.scan(TableName="app_data")
    items = resp.get("Items", [])
    assert len(items) == 2
    pks = sorted(_flatten(item["PK"]) for item in items)
    assert pks == ["AUDIT#2026-06-23", "AUDIT#2026-06-24"]


@pytest.mark.asyncio
async def test_event_id_is_unique(
    audit_logger: AuditLogger,
    ddb_client: Any,
) -> None:
    request = _make_request()
    await audit_logger.log(
        "evt-a", actor_sub=None, session_code=None, details={}, request=request
    )
    await audit_logger.log(
        "evt-b", actor_sub=None, session_code=None, details={}, request=request
    )
    await audit_logger.drain()

    resp = ddb_client.scan(TableName="app_data")
    event_ids = {_flatten(item["event_id"]) for item in resp.get("Items", [])}
    assert len(event_ids) == 2
    for eid in event_ids:
        uuid.UUID(eid)  # parses as UUIDv4


@pytest.mark.asyncio
async def test_write_failure_does_not_raise() -> None:
    """Fire-and-forget semantics: a repository failure must be swallowed."""

    flaky_repo = MagicMock()
    flaky_repo.write.side_effect = RuntimeError("dynamodb down")
    logger = AuditLogger.__new__(AuditLogger)
    logger._repo = flaky_repo  # noqa: SLF001 — intentional test hook
    logger._pending = set()  # noqa: SLF001

    request = _make_request()
    # Must not raise — the background task swallows exceptions internally
    await logger.log(
        "evt", actor_sub=None, session_code=None, details={}, request=request
    )
    # Give the background task a chance to execute
    await asyncio.sleep(0.05)
    if logger._pending:  # noqa: SLF001
        await asyncio.gather(*logger._pending, return_exceptions=True)


def _flatten(dynamo_value: Any) -> str:
    """Unwrap a low-level DynamoDB attribute value (e.g. ``{"S": "x"}``)."""
    if isinstance(dynamo_value, dict):
        s_value = dynamo_value.get("S")
        if isinstance(s_value, str):
            return s_value
    return str(dynamo_value)
