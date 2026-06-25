"""Tests for ``app.middleware.rbac`` (Task 2.4).

Exercises ``require_role`` end-to-end via a test FastAPI app with
three protected routes (Manager-only, Session Admin-on-{code},
Driver-on-{code}). The ``ddb_client`` fixture from ``tests/conftest.py``
pre-creates the moto-mocked ``app_data`` table; tests populate the
``ADMIN#<sub>`` / ``REG#<sub>`` items directly via ``put_item`` to model
session-scoped role assignments.

The matrix below maps each parametrized case to the RBAC expectation.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from moto import mock_aws

from app.auth.jwt import create_app_token
from app.db import get_ddb_client
from app.middleware.rbac import compute_effective_roles, require_role
from app.models.auth import GoogleUser, TokenPayload
from app.models.roles import Role

_TEST_SECRET = "test-secret-32-bytes-min-length-aaaa"
_TEST_SUB = "testsub"
_TEST_SUB_OTHER = "testsub-other"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _TEST_SECRET)


def _make_token(sub: str, *, global_role: str) -> str:
    return create_app_token(
        GoogleUser(sub=sub, email=f"{sub}@example.com", name=sub.title()),
        global_role=global_role,
    )


def _put_admin(client: Any, session_code: str, sub: str) -> None:
    client.put_item(
        TableName="app_data",
        Item={
            "PK": {"S": f"SESSION#{session_code}"},
            "SK": {"S": f"ADMIN#{sub}"},
            "assigned_by": {"S": "system"},
        },
    )


def _put_registration(
    client: Any,
    session_code: str,
    sub: str,
    *,
    role: str,
) -> None:
    client.put_item(
        TableName="app_data",
        Item={
            "PK": {"S": f"SESSION#{session_code}"},
            "SK": {"S": f"REG#{sub}"},
            "role": {"S": role},
        },
    )


def _put_user(client: Any, sub: str, *, global_roles: list[str]) -> None:
    client.put_item(
        TableName="app_data",
        Item={
            "PK": {"S": f"USER#{sub}"},
            "SK": {"S": "METADATA"},
            "global_roles": {"L": [{"S": r} for r in global_roles]},
        },
    )


def _build_test_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(HTTPException)
    async def _envelope_http_exception(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if (
            isinstance(detail, dict)
            and set(detail.keys()) == {"error"}
            and isinstance(detail["error"], dict)
        ):
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )

    @app.get("/manager-only")
    async def manager_only(
        user: TokenPayload = Depends(require_role(Role.MANAGER)),
    ) -> dict[str, str]:
        return {"sub": user.sub}

    @app.get("/sessions/{code}/admin")
    async def admin_route(
        user: TokenPayload = Depends(require_role(Role.SESSION_ADMIN)),
    ) -> dict[str, str]:
        return {"sub": user.sub}

    @app.get("/sessions/{code}/driver")
    async def driver_route(
        user: TokenPayload = Depends(require_role(Role.DRIVER)),
    ) -> dict[str, str]:
        return {"sub": user.sub}

    @app.get("/sessions/{code}/passenger")
    async def passenger_route(
        user: TokenPayload = Depends(require_role(Role.PASSENGER)),
    ) -> dict[str, str]:
        return {"sub": user.sub}

    return app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with mock_aws():
        import boto3

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

        app = _build_test_app()
        app.dependency_overrides[get_ddb_client] = lambda: ddb
        with TestClient(app) as test_client:
            test_client.ddb = ddb
            yield test_client


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _body(resp: Any) -> Any:
    return resp.json()


# ---------------------------------------------------------------------------
# Test matrix
# ---------------------------------------------------------------------------


def test_superuser_passes_manager_only(client: TestClient) -> None:
    token = _make_token(_TEST_SUB, global_role="superuser")
    resp = client.get("/manager-only", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert _body(resp) == {"sub": _TEST_SUB}


def test_superuser_passes_admin_route_without_assignment(
    client: TestClient,
) -> None:
    token = _make_token(_TEST_SUB, global_role="superuser")
    resp = client.get("/sessions/ABC/admin", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert _body(resp) == {"sub": _TEST_SUB}


def test_manager_passes_manager_only(client: TestClient) -> None:
    token = _make_token(_TEST_SUB, global_role="manager")
    resp = client.get("/manager-only", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_manager_passes_admin_route_via_precedence(client: TestClient) -> None:
    """Manager > Session Admin precedence (§2.2) — no ADMIN# item needed."""
    token = _make_token(_TEST_SUB, global_role="manager")
    resp = client.get("/sessions/ABC/admin", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_session_admin_for_a_can_admin_a(client: TestClient) -> None:
    _put_admin(client.ddb, "ABC", _TEST_SUB)
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/admin", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_session_admin_for_a_gets_403_on_admin_b(client: TestClient) -> None:
    _put_admin(client.ddb, "ABC", _TEST_SUB)
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/DEF/admin", headers=_auth(token))
    assert resp.status_code == 403, resp.text
    body = _body(resp)
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["details"]["required_role"] == "session_admin"
    assert body["error"]["details"]["session_code"] == "DEF"


def test_passenger_gets_403_on_manager_only(client: TestClient) -> None:
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/manager-only", headers=_auth(token))
    assert resp.status_code == 403, resp.text
    body = _body(resp)
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["details"]["required_role"] == "manager"
    assert "session_code" not in body["error"]["details"]


def test_passenger_gets_403_on_admin_route(client: TestClient) -> None:
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="passenger",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/admin", headers=_auth(token))
    assert resp.status_code == 403, resp.text
    body = _body(resp)
    assert body["error"]["details"]["required_role"] == "session_admin"


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.get("/manager-only")
    assert resp.status_code == 401, resp.text
    body = _body(resp)
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_driver_gets_403_on_manager_only(client: TestClient) -> None:
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/manager-only", headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_driver_in_a_can_access_driver_route_on_a(client: TestClient) -> None:
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/driver", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_global_none_registered_as_driver_in_a_passes_driver_route(
    client: TestClient,
) -> None:
    """``global_role='none'`` + Driver registration → Driver check passes."""
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/driver", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_driver_in_a_is_denied_driver_route_on_b(client: TestClient) -> None:
    """Session scoping: Driver in A does NOT satisfy Driver check on B."""
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/DEF/driver", headers=_auth(token))
    assert resp.status_code == 403, resp.text


def test_driver_in_a_satisfies_passenger_route_on_a(client: TestClient) -> None:
    """Precedence rule: Driver (40) satisfies Passenger (20)."""
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/passenger", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_session_admin_in_a_satisfies_passenger_route_on_a(
    client: TestClient,
) -> None:
    """Precedence rule: Session Admin (60) satisfies Passenger (20)."""
    _put_admin(client.ddb, "ABC", _TEST_SUB)
    token = _make_token(_TEST_SUB, global_role="none")
    resp = client.get("/sessions/ABC/passenger", headers=_auth(token))
    assert resp.status_code == 200, resp.text


def test_garbage_bearer_token_returns_401(client: TestClient) -> None:
    """Auth runs before RBAC; bad token never reaches the role check."""
    resp = client.get("/manager-only", headers=_auth("not-a-jwt"))
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# compute_effective_roles unit tests (cover the precedence-expansion branch
# without a request, exercising both the global and session-scoped paths).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_effective_roles_superuser_no_ddb_needed() -> None:
    """``superuser`` global role → no DynamoDB lookup; set is just SUPERUSER.

    Precedence is enforced by ``Role.satisfies()`` in ``require_role`` —
    the effective set does not need to contain lower-ranked roles to
    pass a lower-ranked check.
    """
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="superuser",
        exp=9999999999,
    )
    effective = await compute_effective_roles(payload, None, ddb_client=None)  # type: ignore[arg-type]
    assert effective == {Role.SUPERUSER}


@pytest.mark.asyncio
async def test_compute_effective_roles_manager_no_ddb_needed() -> None:
    """``manager`` global role → no DynamoDB lookup even with session_code."""
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="manager",
        exp=9999999999,
    )
    effective = await compute_effective_roles(payload, "ABC", ddb_client=None)  # type: ignore[arg-type]
    assert effective == {Role.MANAGER}


@pytest.mark.asyncio
async def test_compute_effective_roles_session_admin_includes_lower(
    client: TestClient,
) -> None:
    """``ADMIN#`` item present → SESSION_ADMIN + precedence expansion."""
    _put_admin(client.ddb, "ABC", _TEST_SUB)
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="none",
        exp=9999999999,
    )
    effective = await compute_effective_roles(
        payload,
        "ABC",
        client.ddb,
    )
    assert effective == {Role.SESSION_ADMIN, Role.DRIVER, Role.PASSENGER}


@pytest.mark.asyncio
async def test_compute_effective_roles_driver_registration_includes_passenger(
    client: TestClient,
) -> None:
    """``REG#`` (role=driver) → DRIVER + PASSENGER (precedence)."""
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="driver",
    )
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="none",
        exp=9999999999,
    )
    effective = await compute_effective_roles(
        payload,
        "ABC",
        client.ddb,
    )
    assert effective == {Role.DRIVER, Role.PASSENGER}


@pytest.mark.asyncio
async def test_compute_effective_roles_passenger_registration_only_passenger(
    client: TestClient,
) -> None:
    """``REG#`` (role=passenger) → PASSENGER only (no lower to expand)."""
    _put_registration(
        client.ddb,
        "ABC",
        _TEST_SUB,
        role="passenger",
    )
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="none",
        exp=9999999999,
    )
    effective = await compute_effective_roles(
        payload,
        "ABC",
        client.ddb,
    )
    assert effective == {Role.PASSENGER}


@pytest.mark.asyncio
async def test_compute_effective_roles_none_no_session_code_empty(
    client: TestClient,
) -> None:
    """``global_role='none'`` and no session_code → empty effective set."""
    payload = TokenPayload(
        sub=_TEST_SUB,
        email="a@example.com",
        name="A",
        global_role="none",
        exp=9999999999,
    )
    effective = await compute_effective_roles(
        payload,
        None,
        client.ddb,
    )
    assert effective == set()
