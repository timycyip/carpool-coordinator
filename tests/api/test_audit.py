"""Audit API tests — ``GET /audit`` (API contracts §3.16).

Covers the read endpoint only. The middleware tests (fire-and-forget
writes) live in ``tests/middleware/test_audit.py``.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.auth.jwt import create_app_token
from app.db import get_ddb_client
from app.main import app
from app.models.auth import GoogleUser
from app.repositories.audit import AuditRepository

_TEST_SECRET = "test-secret-32-bytes-min-length-aaaa"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _TEST_SECRET)


def _make_token(sub: str = "testuser", *, global_role: str = "superuser") -> str:
    return create_app_token(
        GoogleUser(sub=sub, email=f"{sub}@example.com", name=sub.title()),
        global_role=global_role,
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_audit_items(client: Any) -> None:
    """Write a small fixed corpus of audit events for filter assertions."""
    repo = AuditRepository(table_name="app_data", client=client)
    repo_write = repo.write

    async def seed() -> None:
        await repo_write(
            "2026-06-24",
            "evt-001",
            {
                "event_id": "evt-001",
                "timestamp": "2026-06-24T10:00:00+00:00",
                "actor_sub": "user-1",
                "event_type": "auth.login.success",
                "session_code": None,
                "ip_address": "1.1.1.1",
                "details": {"method": "google"},
            },
        )
        await repo_write(
            "2026-06-24",
            "evt-002",
            {
                "event_id": "evt-002",
                "timestamp": "2026-06-24T11:00:00+00:00",
                "actor_sub": "user-2",
                "event_type": "session.created",
                "session_code": "ABC123",
                "ip_address": "2.2.2.2",
                "details": {"title": "Sunday Service"},
            },
        )
        await repo_write(
            "2026-06-24",
            "evt-003",
            {
                "event_id": "evt-003",
                "timestamp": "2026-06-24T12:00:00+00:00",
                "actor_sub": "user-1",
                "event_type": "session.updated",
                "session_code": "ABC123",
                "ip_address": "1.1.1.1",
                "details": {"field": "status"},
            },
        )
        await repo_write(
            "2026-06-25",
            "evt-004",
            {
                "event_id": "evt-004",
                "timestamp": "2026-06-25T09:00:00+00:00",
                "actor_sub": "user-3",
                "event_type": "auth.login.success",
                "session_code": None,
                "ip_address": "3.3.3.3",
                "details": {"method": "google"},
            },
        )

    import asyncio

    asyncio.run(seed())


def _seed_many_audit_items(client: Any) -> None:
    """Seed 5 items on the same day for pagination cursor testing."""
    repo = AuditRepository(table_name="app_data", client=client)
    repo_write = repo.write

    async def seed() -> None:
        for i in range(1, 6):
            await repo_write(
                "2026-06-24",
                f"pag-evt-{i:03d}",
                {
                    "event_id": f"pag-evt-{i:03d}",
                    "timestamp": f"2026-06-24T{i + 9:02d}:00:00+00:00",
                    "actor_sub": f"user-{i}",
                    "event_type": "auth.login.success",
                    "session_code": None,
                    "ip_address": f"10.0.0.{i}",
                    "details": {"seq": i},
                },
            )

    import asyncio

    asyncio.run(seed())


@pytest.fixture()
def audit_client(ddb_client: Any) -> Generator[TestClient, None, None]:
    """TestClient backed by moto-mocked DynamoDB with audit items seeded."""
    _seed_audit_items(ddb_client)
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_unauthenticated_returns_401(audit_client: TestClient) -> None:
    """GET /audit requires authentication (RBAC via require_role)."""
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24"},
    )
    assert response.status_code == 401


def test_passenger_returns_403(audit_client: TestClient) -> None:
    """Passenger (global_role=none) cannot read audit logs."""
    token = _make_token(global_role="none")
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24"},
        headers=_auth(token),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


def test_superuser_can_read_audit(audit_client: TestClient) -> None:
    """Superuser can read audit logs (global role, no session scope needed)."""
    token = _make_token(global_role="superuser")
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24", "limit": 50},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 3


def test_manager_can_read_audit(audit_client: TestClient) -> None:
    """Manager can read audit logs (precedence: Manager > Session Admin)."""
    token = _make_token(global_role="manager")
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24"},
        headers=_auth(token),
    )
    assert response.status_code == 200


def test_get_audit_returns_paginated_results(audit_client: TestClient) -> None:
    token = _make_token()
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24", "limit": 50},
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "limit" in body
    assert body["limit"] == 50
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 3


def test_get_audit_event_type_filter(audit_client: TestClient) -> None:
    token = _make_token()
    response = audit_client.get(
        "/audit",
        params={
            "from": "2026-06-24",
            "to": "2026-06-24",
            "event_type": "session.created",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["event_type"] == "session.created"
    assert items[0]["session_code"] == "ABC123"


def test_get_audit_date_range(audit_client: TestClient) -> None:
    """Same-day range returns all events; a wider window is accepted."""
    token = _make_token()
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 3


def test_invalid_audit_date_returns_client_error(audit_client: TestClient) -> None:
    response = audit_client.get(
        "/audit",
        params={"from": "not-a-date"},
        headers=_auth(_make_token()),
    )
    assert response.status_code == 400


def test_get_audit_empty_when_no_events(ddb_client: Any) -> None:
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as client:
        token = _make_token()
        response = client.get(
            "/audit",
            params={"from": "2026-06-24", "to": "2026-06-24"},
            headers=_auth(token),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None
    assert body["limit"] == 50


def test_get_audit_session_code_filter(audit_client: TestClient) -> None:
    token = _make_token()
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24", "session_code": "ABC123"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    for item in items:
        assert item["session_code"] == "ABC123"


def test_get_audit_limit_respected(audit_client: TestClient) -> None:
    token = _make_token()
    response = audit_client.get(
        "/audit",
        params={"from": "2026-06-24", "to": "2026-06-24", "limit": 2},
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["limit"] == 2


def test_pagination_cursor_returns_next_page_without_skipping() -> None:
    """Bug fix: next_cursor must point to the last RETURNED item's SK,
    not the last item of the day. Otherwise the next page skips rows.

    Seeds 5 items on one day, queries limit=2, then uses the cursor
    to get the next page and verifies no items are skipped.
    """
    with mock_aws():
        ddb = boto3.client("dynamodb", region_name="us-east-2")
        ddb.create_table(
            TableName="app_data",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        ddb.create_table(
            TableName="rate_limit_cache",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        _seed_many_audit_items(ddb)
        app.dependency_overrides[get_ddb_client] = lambda: ddb

        with TestClient(app) as client:
            token = _make_token()

            # Page 1: get first 2 items
            resp1 = client.get(
                "/audit",
                params={"from": "2026-06-24", "to": "2026-06-24", "limit": 2},
                headers=_auth(token),
            )
            assert resp1.status_code == 200
            page1 = resp1.json()
            assert len(page1["items"]) == 2
            assert page1["next_cursor"] is not None

            # Page 2: get remaining items
            resp2 = client.get(
                "/audit",
                params={
                    "from": "2026-06-24",
                    "to": "2026-06-24",
                    "limit": 2,
                    "cursor": page1["next_cursor"],
                },
                headers=_auth(token),
            )
            assert resp2.status_code == 200
            page2 = resp2.json()
            assert len(page2["items"]) == 2

            # Page 3: last item
            if page2["next_cursor"] is not None:
                resp3 = client.get(
                    "/audit",
                    params={
                        "from": "2026-06-24",
                        "to": "2026-06-24",
                        "limit": 2,
                        "cursor": page2["next_cursor"],
                    },
                    headers=_auth(token),
                )
                assert resp3.status_code == 200
                page3 = resp3.json()
                all_items = page1["items"] + page2["items"] + page3["items"]
            else:
                all_items = page1["items"] + page2["items"]

            # All 5 items returned, no duplicates
            event_ids = [item["event_id"] for item in all_items]
            assert len(event_ids) == 5, (
                f"Expected 5 items total, got {len(event_ids)}: {event_ids}"
            )
            assert len(set(event_ids)) == 5, f"Duplicate items found: {event_ids}"

        app.dependency_overrides.clear()


def test_pagination_cursor_continues_into_later_date_partition(
    audit_client: TestClient,
) -> None:
    token = _make_token()
    params = {"from": "2026-06-24", "to": "2026-06-25", "limit": 3}

    first_page = audit_client.get("/audit", params=params, headers=_auth(token))
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 3
    assert first_body["next_cursor"] is not None

    second_page = audit_client.get(
        "/audit",
        params={**params, "cursor": first_body["next_cursor"]},
        headers=_auth(token),
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert [item["event_id"] for item in second_body["items"]] == ["evt-004"]
    assert second_body["next_cursor"] is None
