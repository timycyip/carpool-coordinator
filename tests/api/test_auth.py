"""Tests for ``POST /auth/google`` (API contract §3.1).

The OIDC verifier is patched to bypass network calls; only the API-level
behavior (payload validation, user upsert, response shape, error envelope)
is exercised here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.auth import oidc as oidc_module
from app.db import get_ddb_client
from app.main import app
from app.middleware.audit import AuditLogger, audit_dependency
from app.models.auth import GoogleUser
from app.repositories.audit import AuditRepository

_AUDIENCE = "test-client-id.apps.googleusercontent.com"


class _SyncAuditLogger(AuditLogger):
    """Test-only subclass that writes audit events synchronously.

    The production AuditLogger uses ``asyncio.create_task`` for
    fire-and-forget writes. In tests the background task may not
    complete before assertions run. This subclass ``await``s the
    write directly so the event is in DynamoDB when the response
    is returned.
    """

    async def log(
        self,
        event_type: str,
        actor_sub: str | None,
        session_code: str | None,
        details: dict[str, Any],
        request: Any,
    ) -> None:
        import sys
        import uuid
        from datetime import datetime, timezone

        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        ip_address = "127.0.0.1"
        attrs: dict[str, Any] = {
            "event_id": event_id,
            "timestamp": timestamp,
            "actor_sub": actor_sub,
            "event_type": event_type,
            "session_code": session_code,
            "ip_address": ip_address,
            "details": details,
        }
        date_str = timestamp[:10]
        try:
            await self._repo.write(date_str, event_id, attrs)
        except Exception as exc:
            print(f"audit write failed: {exc!r}", file=sys.stderr)


@pytest.fixture()
def auth_client(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> Generator[TestClient, None, None]:
    """TestClient backed by the conftest's moto-mocked DynamoDB and a fake
    Google OIDC verifier. Both fixtures share the same ``mock_aws`` context
    (the ``ddb_client`` fixture sets it up; ``auth_client`` only adds the
    dependency override and the OIDC patch).
    """
    monkeypatch.setenv("GOOGLE_CLIENT_ID", _AUDIENCE)
    monkeypatch.setenv("JWT_SECRET", "test-secret-32-bytes-min-length-aaaa")
    oidc_module._reset_cache_for_tests()

    def _fake_verify(token: str) -> GoogleUser:
        if token == "valid-token":
            return GoogleUser(
                sub="google-sub-123",
                email="alice@example.com",
                name="Alice Anderson",
            )
        if token == "no-name-token":
            return GoogleUser(
                sub="google-sub-456",
                email="bob@example.com",
                name="bob@example.com",
            )
        raise oidc_module.InvalidTokenError("simulated failure")

    monkeypatch.setattr(auth_api, "verify_google_token", _fake_verify)
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    app.dependency_overrides[audit_dependency] = lambda: _SyncAuditLogger(
        client=ddb_client
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_valid_token_returns_200_and_jwt(auth_client: TestClient) -> None:
    response = auth_client.post("/auth/google", json={"id_token": "valid-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["sub"] == "google-sub-123"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["name"] == "Alice Anderson"
    assert body["user"]["global_role"] == "none"

    # The access_token must be a valid HS256 JWT signed with JWT_SECRET.
    claims = pyjwt.decode(
        body["access_token"],
        "test-secret-32-bytes-min-length-aaaa",
        algorithms=["HS256"],
    )
    assert claims["sub"] == "google-sub-123"
    assert claims["email"] == "alice@example.com"
    assert claims["global_role"] == "none"
    assert claims["exp"] - claims["iat"] == 3600


def test_invalid_google_token_returns_401_envelope(
    auth_client: TestClient,
) -> None:
    response = auth_client.post("/auth/google", json={"id_token": "garbage"})
    assert response.status_code == 401
    body = response.json()
    assert body == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Google ID token verification failed.",
            "details": {"reason": "invalid_google_token"},
        }
    }


def test_missing_id_token_returns_422(auth_client: TestClient) -> None:
    response = auth_client.post("/auth/google", json={})
    assert response.status_code == 422


def test_empty_id_token_returns_422(auth_client: TestClient) -> None:
    response = auth_client.post("/auth/google", json={"id_token": ""})
    assert response.status_code == 422


def test_missing_body_returns_422(auth_client: TestClient) -> None:
    response = auth_client.post("/auth/google")
    assert response.status_code == 422


def test_user_is_upserted_in_dynamodb(auth_client: TestClient, ddb_client: Any) -> None:
    auth_client.post("/auth/google", json={"id_token": "valid-token"})

    item = ddb_client.get_item(
        TableName="app_data",
        Key={"PK": {"S": "USER#google-sub-123"}, "SK": {"S": "METADATA"}},
    )["Item"]
    assert item["email"]["S"] == "alice@example.com"
    assert item["name"]["S"] == "Alice Anderson"
    assert item["global_roles"]["L"] == []


def test_second_login_updates_existing_user(
    auth_client: TestClient, ddb_client: Any
) -> None:
    """Re-login preserves the user record and reuses the same partition."""
    auth_client.post("/auth/google", json={"id_token": "valid-token"})
    auth_client.post("/auth/google", json={"id_token": "valid-token"})

    resp = ddb_client.query(
        TableName="app_data",
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": {"S": "USER#google-sub-123"}},
    )
    items = resp["Items"]
    assert len(items) == 1
    assert items[0]["email"]["S"] == "alice@example.com"


def test_jwt_uses_granted_global_role(auth_client: TestClient, ddb_client: Any) -> None:
    """If a user has a granted global_role in DynamoDB, the JWT reflects it."""
    ddb_client.put_item(
        TableName="app_data",
        Item={
            "PK": {"S": "USER#google-sub-123"},
            "SK": {"S": "METADATA"},
            "email": {"S": "alice@example.com"},
            "name": {"S": "Alice Anderson"},
            "global_roles": {"L": [{"S": "manager"}]},
            "created_at": {"S": "2026-06-24T00:00:00+00:00"},
        },
    )

    response = auth_client.post("/auth/google", json={"id_token": "valid-token"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["global_role"] == "manager"
    claims = pyjwt.decode(
        body["access_token"],
        "test-secret-32-bytes-min-length-aaaa",
        algorithms=["HS256"],
    )
    assert claims["global_role"] == "manager"


def _query_audit_events(ddb_client: Any) -> list[dict[str, Any]]:
    """Query all audit events from the current date partition."""
    from datetime import datetime, timezone

    repo = AuditRepository(table_name="app_data", client=ddb_client)
    today = datetime.now(tz=timezone.utc).date().isoformat()

    async def fetch() -> list[dict[str, Any]]:
        return await repo.query_audit(today)

    return asyncio.run(fetch())


def test_successful_login_writes_auth_login_success_audit_event(
    auth_client: TestClient, ddb_client: Any
) -> None:
    """POST /auth/google with a valid token must write an auth.login.success audit event."""
    response = auth_client.post("/auth/google", json={"id_token": "valid-token"})
    assert response.status_code == 200

    events = _query_audit_events(ddb_client)
    success_events = [e for e in events if e.get("event_type") == "auth.login.success"]
    assert len(success_events) == 1
    evt = success_events[0]
    assert evt["actor_sub"] == "google-sub-123"
    assert evt["session_code"] is None
    assert evt["ip_address"] is not None


def test_failed_login_writes_auth_login_failure_audit_event(
    auth_client: TestClient, ddb_client: Any
) -> None:
    """POST /auth/google with an invalid token must write an auth.login.failure audit event."""
    response = auth_client.post("/auth/google", json={"id_token": "garbage"})
    assert response.status_code == 401

    events = _query_audit_events(ddb_client)
    failure_events = [e for e in events if e.get("event_type") == "auth.login.failure"]
    assert len(failure_events) == 1
    evt = failure_events[0]
    assert evt["actor_sub"] is None
    assert evt["details"]["reason"] == "invalid_google_token"
