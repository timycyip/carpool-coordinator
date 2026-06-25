"""Tests for ``app.middleware.auth.get_current_user`` dependency.

Exercises the Bearer-token parsing and JWT validation paths without
needing a real route — the dependency is invoked directly with a
``Request`` stub.
"""

from __future__ import annotations

import time
from typing import Any, cast

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.jwt import create_app_token
from app.middleware.auth import get_current_user
from app.models.auth import GoogleUser

_TEST_SECRET = "test-secret-32-bytes-min-length-aaaa"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _TEST_SECRET)


def _request_with(headers: dict[str, str]) -> Request:
    """Build a minimal Starlette ``Request`` with the given headers."""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
    }
    return Request(scope)


def _unauthorized(exc: BaseException) -> dict[str, Any]:
    """Extract the canonical ``ErrorResponse`` envelope from a raised HTTPException."""
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 401
    assert isinstance(exc.detail, dict)
    return cast(dict[str, Any], exc.detail)


def test_valid_bearer_token_returns_payload() -> None:
    user = GoogleUser(sub="abc", email="a@example.com", name="Alice")
    token = create_app_token(user, global_role="manager")
    request = _request_with({"Authorization": f"Bearer {token}"})

    payload = get_current_user(request)

    assert payload.sub == "abc"
    assert payload.email == "a@example.com"
    assert payload.name == "Alice"
    assert payload.global_role == "manager"


def test_missing_authorization_header_returns_401() -> None:
    request = _request_with({})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    body = _unauthorized(exc_info.value)
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["details"]["reason"] == "missing_bearer_token"


def test_non_bearer_scheme_returns_401() -> None:
    request = _request_with({"Authorization": "Basic dXNlcjpwYXNz"})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    body = _unauthorized(exc_info.value)
    assert body["error"]["details"]["reason"] == "malformed_bearer_token"


def test_malformed_bearer_returns_401() -> None:
    request = _request_with({"Authorization": "Bearer"})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    body = _unauthorized(exc_info.value)
    assert body["error"]["details"]["reason"] == "malformed_bearer_token"


def test_garbage_token_returns_401() -> None:
    request = _request_with({"Authorization": "Bearer not-a-jwt"})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    body = _unauthorized(exc_info.value)
    assert body["error"]["details"]["reason"] == "invalid_token"


def test_expired_token_returns_401() -> None:
    now = int(time.time()) - 7200
    token = pyjwt.encode(
        {
            "sub": "abc",
            "email": "a@example.com",
            "name": "Alice",
            "global_role": "none",
            "iat": now,
            "exp": now + 60,
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    request = _request_with({"Authorization": f"Bearer {token}"})
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(request)
    body = _unauthorized(exc_info.value)
    assert body["error"]["details"]["reason"] == "token_expired"
