"""Tests for ``app.auth.jwt`` (create / decode app session JWT)."""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest

from app.auth.jwt import (
    InvalidAppTokenError,
    create_app_token,
    decode_app_token,
)
from app.models.auth import GoogleUser

_TEST_SECRET = "unit-test-jwt-secret-32-bytes-min!!"


@pytest.fixture(autouse=True)
def _set_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _TEST_SECRET)


def test_round_trip_returns_payload() -> None:
    user = GoogleUser(sub="abc", email="a@example.com", name="Alice")
    token = create_app_token(user, global_role="manager")

    payload = decode_app_token(token)

    assert payload.sub == "abc"
    assert payload.email == "a@example.com"
    assert payload.name == "Alice"
    assert payload.global_role == "manager"
    assert payload.exp > int(time.time())


def test_payload_contains_correct_claims() -> None:
    user = GoogleUser(sub="abc", email="a@example.com", name="Alice")
    token = create_app_token(user, global_role="superuser")

    raw = pyjwt.decode(token, _TEST_SECRET, algorithms=["HS256"])
    assert raw["sub"] == "abc"
    assert raw["email"] == "a@example.com"
    assert raw["name"] == "Alice"
    assert raw["global_role"] == "superuser"
    assert "iat" in raw
    assert raw["exp"] - raw["iat"] == 3600


def test_expired_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a token that expired in the past by setting the issued-at far in
    # the past and a negative expires_in. We bypass ``create_app_token`` so we
    # don't have to monkey-patch ``time.time``.
    import jwt as pyjwt_mod

    now = int(time.time()) - 7200
    token = pyjwt_mod.encode(
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
    with pytest.raises(InvalidAppTokenError, match="expired"):
        decode_app_token(token)


def test_tampered_token_raises() -> None:
    user = GoogleUser(sub="abc", email="a@example.com", name="Alice")
    token = create_app_token(user)

    head, payload, signature = token.split(".")
    tampered = f"{head}.{payload}.{signature[:-4]}ZZZZ"

    with pytest.raises(InvalidAppTokenError):
        decode_app_token(tampered)


def test_wrong_secret_raises() -> None:
    token = pyjwt.encode(
        {
            "sub": "abc",
            "email": "a@example.com",
            "name": "Alice",
            "global_role": "none",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(InvalidAppTokenError):
        decode_app_token(token)


def test_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    user = GoogleUser(sub="abc", email="a@example.com", name="Alice")
    with pytest.raises(InvalidAppTokenError, match="JWT_SECRET"):
        create_app_token(user)


def test_missing_claims_raises() -> None:
    import jwt as pyjwt_mod

    token = pyjwt_mod.encode({"sub": "abc"}, _TEST_SECRET, algorithm="HS256")
    with pytest.raises(InvalidAppTokenError, match="claims"):
        decode_app_token(token)


def test_empty_token_raises() -> None:
    with pytest.raises(InvalidAppTokenError):
        decode_app_token("")
