"""Tests for the DynamoDB-backed rate limiting middleware.

Covers ``app.middleware.rate_limit`` per ``docs/api_contracts.md`` §1.4
and FR §14 (60 req/min/IP, 120 req/min/user). Each test exercises the
``rate_limit_dependency`` through a tiny FastAPI app so we can assert
on the wire-level response (status, headers, envelope).
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.auth.jwt import create_app_token
from app.db import get_ddb_client
from app.middleware.rate_limit import (
    RateLimitExceeded,
    RateLimiter,
    rate_limit_dependency,
)
from app.models.auth import GoogleUser

_TEST_SECRET = "test-secret-32-bytes-min-length-aaaa"

# Default limits — overridden per-test via env vars below.
_DEFAULT_IP_LIMIT = 60
_DEFAULT_USER_LIMIT = 120


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _TEST_SECRET)


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.exception_handler(HTTPException)
    async def _envelope(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if (
            isinstance(detail, dict)
            and set(detail.keys()) == {"error"}
            and isinstance(detail["error"], dict)
        ):
            return JSONResponse(
                status_code=exc.status_code, content=detail, headers=exc.headers
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )

    @app.get("/ping")
    async def ping(
        _rl: None = Depends(rate_limit_dependency),
    ) -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture()
def rl_app(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> Generator[TestClient, None, None]:
    """A TestClient with the rate-limit dependency bound to moto DynamoDB."""
    monkeypatch.setenv("RATE_LIMIT_PER_IP", str(_DEFAULT_IP_LIMIT))
    monkeypatch.setenv("RATE_LIMIT_PER_USER", str(_DEFAULT_USER_LIMIT))
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "60")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "60")
    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _bearer(sub: str = "user-1") -> str:
    user = GoogleUser(sub=sub, email=f"{sub}@example.com", name=sub.title())
    return create_app_token(user, global_role="none")


def test_first_request_passes(rl_app: TestClient) -> None:
    response = rl_app.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_limit_boundary_60th_passes_61st_rejected(
    rl_app: TestClient, ddb_client: Any
) -> None:
    headers = {"X-Forwarded-For": "10.0.0.2"}

    for _ in range(_DEFAULT_IP_LIMIT):
        response = rl_app.get("/ping", headers=headers)
        assert response.status_code == 200

    response = rl_app.get("/ping", headers=headers)
    assert response.status_code == 429

    body = response.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["details"]["limit"] == _DEFAULT_IP_LIMIT
    assert body["error"]["details"]["remaining"] == 0
    assert body["error"]["details"]["retry_after_seconds"] >= 1

    assert "Retry-After" in response.headers
    assert response.headers["X-RateLimit-Limit"] == str(_DEFAULT_IP_LIMIT)
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["X-RateLimit-Reset"]) > int(time.time())


def test_per_ip_and_per_user_buckets_independent(rl_app: TestClient) -> None:
    """Exhausting the IP bucket must not affect the user bucket (different sub)."""
    headers_ip_only = {"X-Forwarded-For": "10.0.0.3"}
    headers_auth = {
        "X-Forwarded-For": "10.0.0.4",
        "Authorization": f"Bearer {_bearer(sub='alice')}",
    }

    for _ in range(_DEFAULT_IP_LIMIT):
        rl_app.get("/ping", headers=headers_ip_only)
    blocked = rl_app.get("/ping", headers=headers_ip_only)
    assert blocked.status_code == 429

    response = rl_app.get("/ping", headers=headers_auth)
    assert response.status_code == 200


def test_authenticated_request_exhausts_user_bucket_independently(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    """Per-user bucket is checked in addition to per-IP — exceeding the
    user limit must return 429 even when the IP still has capacity.

    Uses distinct IPs per request so the per-IP bucket never trips
    (each IP is below the limit) while the user bucket fills up.
    """
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "10000")
    monkeypatch.setenv("RATE_LIMIT_PER_USER", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "60")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "60")

    sub = "bob"
    token = _bearer(sub=sub)

    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as c:
        for i in range(3):
            response = c.get(
                "/ping",
                headers={
                    "X-Forwarded-For": f"10.0.0.{i + 10}",
                    "Authorization": f"Bearer {token}",
                },
            )
            assert response.status_code == 200, response.text

        response = c.get(
            "/ping",
            headers={
                "X-Forwarded-For": "10.0.0.99",
                "Authorization": f"Bearer {token}",
            },
        )
        assert response.status_code == 429

        body = response.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        assert body["error"]["details"]["limit"] == 3
        assert response.headers["X-RateLimit-Limit"] == "3"
        assert response.headers["X-RateLimit-Remaining"] == "0"

        other_token = _bearer(sub="carol")
        response = c.get(
            "/ping",
            headers={
                "X-Forwarded-For": "10.0.0.100",
                "Authorization": f"Bearer {other_token}",
            },
        )
        assert response.status_code == 200
    app.dependency_overrides.clear()


def test_window_reset_allows_requests_again(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    """After the window boundary advances, the next request must succeed.

    Uses a short 1-second window and a fake ``time.time`` source so the
    boundary advance is deterministic.
    """
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "60")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "60")

    fake_now = {"t": 1_000_000.0}

    def _now() -> float:
        return fake_now["t"]

    monkeypatch.setattr("app.middleware.rate_limit.time.time", _now)

    rl = RateLimiter(client=ddb_client)
    rl.check(ip="10.0.0.10")
    rl.check(ip="10.0.0.10")
    with pytest.raises(RateLimitExceeded):
        rl.check(ip="10.0.0.10")

    fake_now["t"] += 60
    rl.check(ip="10.0.0.10")


def test_xff_header_takes_precedence_over_request_host(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    """``X-Forwarded-For`` is trusted; otherwise the request's socket host is used."""
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "60")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "60")

    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client

    rl_a = RateLimiter(client=ddb_client)
    rl_a.check(ip="203.0.113.7")
    rl_a.check(ip="203.0.113.7")

    with TestClient(app) as c:
        first = c.get(
            "/ping",
            headers={"X-Forwarded-For": "203.0.113.7"},
        )
        second = c.get(
            "/ping",
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
    app.dependency_overrides.clear()

    assert first.status_code == 429
    assert second.status_code == 200


def test_xff_first_value_used_when_multiple_present(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    """When the header carries a comma-separated chain, only the first IP counts."""
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "60")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "60")

    rl = RateLimiter(client=ddb_client)
    rl.check(ip="203.0.113.9")
    rl.check(ip="203.0.113.9")

    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as c:
        response = c.get(
            "/ping",
            headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1, 10.0.0.2"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 429


def test_invalid_bearer_is_treated_as_anonymous(rl_app: TestClient) -> None:
    """A malformed bearer must not 500 — fall back to per-IP only."""
    headers = {
        "X-Forwarded-For": "10.0.0.20",
        "Authorization": "Bearer not-a-real-jwt",
    }
    response = rl_app.get("/ping", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_429_headers_present(rl_app: TestClient) -> None:
    headers = {"X-Forwarded-For": "10.0.0.30"}
    for _ in range(_DEFAULT_IP_LIMIT):
        rl_app.get("/ping", headers=headers)
    response = rl_app.get("/ping", headers=headers)

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert response.headers["X-RateLimit-Limit"] == str(_DEFAULT_IP_LIMIT)
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert int(response.headers["X-RateLimit-Reset"]) > int(time.time())


def test_default_table_name_is_rate_limit_cache(ddb_client: Any) -> None:
    rl = RateLimiter(client=ddb_client)
    assert rl._table == "rate_limit_cache"  # noqa: SLF001 — internal sanity check


def test_short_window_advances_with_mocked_time(
    monkeypatch: pytest.MonkeyPatch, ddb_client: Any
) -> None:
    """End-to-end via TestClient: 5-second window, fill it, advance clock, retry."""
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "3")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_IP", "5")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_USER", "5")

    fake_now = {"t": 2_000_000.0}

    def _now() -> float:
        return fake_now["t"]

    monkeypatch.setattr("app.middleware.rate_limit.time.time", _now)

    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    headers = {"X-Forwarded-For": "10.0.0.99"}

    with TestClient(app) as c:
        for _ in range(3):
            assert c.get("/ping", headers=headers).status_code == 200
        assert c.get("/ping", headers=headers).status_code == 429

        fake_now["t"] += 5
        assert c.get("/ping", headers=headers).status_code == 200
    app.dependency_overrides.clear()


def test_user_sub_unchanged_when_rate_limit_env_unset(
    ddb_client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dependency must work when env vars are absent (default limits)."""
    for var in (
        "RATE_LIMIT_PER_IP",
        "RATE_LIMIT_PER_USER",
        "RATE_LIMIT_WINDOW_IP",
        "RATE_LIMIT_WINDOW_USER",
    ):
        monkeypatch.delenv(var, raising=False)

    app = _build_app()
    app.dependency_overrides[get_ddb_client] = lambda: ddb_client
    with TestClient(app) as c:
        response = c.get("/ping", headers={"X-Forwarded-For": "10.0.0.50"})
        assert response.status_code == 200
    app.dependency_overrides.clear()


def teardown_module(_module: Any) -> None:
    for var in (
        "RATE_LIMIT_PER_IP",
        "RATE_LIMIT_PER_USER",
        "RATE_LIMIT_WINDOW_IP",
        "RATE_LIMIT_WINDOW_USER",
    ):
        os.environ.pop(var, None)
