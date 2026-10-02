"""Rate limiting middleware (token-bucket on DynamoDB).

Per ``docs/api_contracts.md`` §1.4, every request is bounded by two
counters stored in the ``rate_limit_cache`` DynamoDB table:

- **Per-IP bucket** — ``RATELIMIT#ip:<ip>`` / ``<window_start>``.
  Applied to all requests, including unauthenticated ones (e.g.
  ``/health``, ``/auth/google``).
- **Per-user bucket** — ``RATELIMIT#user:<sub>`` / ``<window_start>``.
  Applied in addition to the per-IP bucket whenever an ``Authorization``
  header carries a valid app session JWT.

Default limits (override via env vars):

- ``RATE_LIMIT_PER_IP``       = 60 requests / window (default 60s)
- ``RATE_LIMIT_PER_USER``     = 120 requests / window (default 60s)
- ``RATE_LIMIT_WINDOW_IP``    = window seconds for IP bucket (default 60)
- ``RATE_LIMIT_WINDOW_USER``  = window seconds for user bucket (default 60)

Implementation notes
--------------------

Counters use atomic ``UpdateItem`` with ``ADD #cnt :inc`` and a
``ConditionExpression`` that permits the increment only when the item
is absent OR the current counter is below the limit. A
``ConditionalCheckFailedException`` therefore signals rate-limit
breach; the limiter raises :class:`RateLimitExceeded`, which the
``rate_limit_dependency`` wraps into the canonical ``429`` envelope.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, Request, status

from app.auth.jwt import InvalidAppTokenError, decode_app_token
from app.config import get_table_name
from app.db import get_ddb_client
from app.models.error import ErrorBody, ErrorResponse

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


_DEFAULT_IP_LIMIT = 60
_DEFAULT_USER_LIMIT = 120
_DEFAULT_WINDOW = 60
_TTL_GRACE_SECONDS = 60


@dataclass(frozen=True)
class RateLimitExceeded(Exception):
    """Raised by :class:`RateLimiter` when a bucket is full.

    Attributes:
        retry_after: Seconds until the current window resets.
        limit: The limit that was exceeded (per-IP or per-user).
        remaining: Always 0 — the request was rejected.
        scope: ``"ip"`` or ``"user"`` — which bucket rejected the request.
    """

    retry_after: int
    limit: int
    remaining: int = 0
    scope: str = "ip"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _extract_ip(request: Request) -> str:
    """Resolve the client IP from ``X-Forwarded-For`` then socket."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _window_start(now: float, window_seconds: int) -> int:
    """Floor ``now`` to the start of the current window."""
    return int(now) - (int(now) % window_seconds)


def _window_end(window_start: int, window_seconds: int) -> int:
    """Exclusive end of the window (= reset timestamp)."""
    return window_start + window_seconds


class RateLimiter:
    """Token-bucket rate limiter backed by DynamoDB.

    The constructor takes a low-level boto3 DynamoDB client (rather than
    a resource) because the low-level API exposes ``ConditionalCheckFailedException``
    via ``ClientError`` more ergonomically than the resource API.

    Configuration values are read from env vars at construction time so
    tests can override them via ``monkeypatch.setenv`` before
    instantiating the limiter.
    """

    def __init__(
        self,
        client: DynamoDBClient,
        table_name: str | None = None,
        ip_limit: int | None = None,
        user_limit: int | None = None,
        ip_window: int | None = None,
        user_window: int | None = None,
    ) -> None:
        self._client = client
        self._table = table_name or get_table_name(
            "RATE_LIMIT_CACHE_TABLE_NAME", "rate_limit_cache"
        )
        self._ip_limit = (
            ip_limit
            if ip_limit is not None
            else _env_int("RATE_LIMIT_PER_IP", _DEFAULT_IP_LIMIT)
        )
        self._user_limit = (
            user_limit
            if user_limit is not None
            else _env_int("RATE_LIMIT_PER_USER", _DEFAULT_USER_LIMIT)
        )
        self._ip_window = (
            ip_window
            if ip_window is not None
            else _env_int("RATE_LIMIT_WINDOW_IP", _DEFAULT_WINDOW)
        )
        self._user_window = (
            user_window
            if user_window is not None
            else _env_int("RATE_LIMIT_WINDOW_USER", _DEFAULT_WINDOW)
        )

    @staticmethod
    def _now() -> float:
        return time.time()

    def _try_increment(
        self,
        pk: str,
        window_start: int,
        window_seconds: int,
        limit: int,
    ) -> None:
        """Atomically increment the counter for ``pk`` (fire-and-forget).

        Raises :class:`RateLimitExceeded` when the bucket is full.
        The return value of ``UpdateItem`` is intentionally discarded —
        the caller only needs a pass/fail signal, which is delivered
        via the exception path.
        """
        ttl = int(self._now()) + window_seconds + _TTL_GRACE_SECONDS
        try:
            self._client.update_item(
                TableName=self._table,
                Key={
                    "PK": {"S": pk},
                    "SK": {"S": str(window_start)},
                },
                UpdateExpression="ADD #cnt :inc SET #ttl = :ttl",
                ConditionExpression="attribute_not_exists(#cnt) OR #cnt < :limit",
                ExpressionAttributeNames={"#cnt": "count", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":inc": {"N": "1"},
                    ":limit": {"N": str(limit)},
                    ":ttl": {"N": str(ttl)},
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                reset_at = _window_end(window_start, window_seconds)
                retry_after = max(1, reset_at - int(self._now()))
                raise RateLimitExceeded(
                    retry_after=retry_after,
                    limit=limit,
                    remaining=0,
                    scope="ip" if pk.startswith("RATELIMIT#ip:") else "user",
                ) from exc
            raise

    def check(self, ip: str, user_sub: str | None = None) -> None:
        """Charge one request against the IP bucket (and user bucket if any).

        Raises :class:`RateLimitExceeded` if either bucket is exhausted.
        """
        now = self._now()

        ip_window_start = _window_start(now, self._ip_window)
        self._try_increment(
            f"RATELIMIT#ip:{ip}",
            ip_window_start,
            self._ip_window,
            self._ip_limit,
        )

        if user_sub is not None:
            user_window_start = _window_start(now, self._user_window)
            self._try_increment(
                f"RATELIMIT#user:{user_sub}",
                user_window_start,
                self._user_window,
                self._user_limit,
            )

    def reset_state(self) -> None:
        """Wipe all rate-limit counters (test helper)."""
        resp = self._client.scan(TableName=self._table)
        for item in resp.get("Items", []):
            self._client.delete_item(
                TableName=self._table,
                Key={"PK": item["PK"], "SK": item["SK"]},
            )

    @property
    def ip_limit(self) -> int:
        return self._ip_limit

    @property
    def user_limit(self) -> int:
        return self._user_limit

    @property
    def ip_window(self) -> int:
        return self._ip_window

    @property
    def user_window(self) -> int:
        return self._user_window


def _build_429(
    exc: RateLimitExceeded,
) -> HTTPException:
    """Format a :class:`RateLimitExceeded` as the canonical 429 envelope."""
    reset_at = int(RateLimiter._now()) + exc.retry_after
    body = ErrorResponse(
        error=ErrorBody(
            code="RATE_LIMITED",
            message=f"Rate limit exceeded. Try again in {exc.retry_after} seconds.",
            details={
                "retry_after_seconds": exc.retry_after,
                "limit": exc.limit,
                "remaining": exc.remaining,
            },
        )
    )
    headers = {
        "Retry-After": str(exc.retry_after),
        "X-RateLimit-Limit": str(exc.limit),
        "X-RateLimit-Remaining": str(exc.remaining),
        "X-RateLimit-Reset": str(reset_at),
    }
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=body.model_dump(),
        headers=headers,
    )


def _extract_user_sub(request: Request) -> str | None:
    """Decode the ``Authorization`` header if present; return ``sub`` or ``None``."""
    header = request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return None
    try:
        payload = decode_app_token(parts[1])
    except InvalidAppTokenError:
        return None
    return payload.sub


def rate_limit_dependency(
    request: Request,
    client: DynamoDBClient = Depends(get_ddb_client),
) -> None:
    """FastAPI dependency enforcing per-IP + per-user rate limits.

    Resolves the client IP, optionally decodes the bearer token to
    identify the user, then charges one request against each applicable
    bucket. Raises ``HTTPException(429)`` with the canonical envelope
    and rate-limit headers on rejection.
    """
    limiter = RateLimiter(client=client)
    ip = _extract_ip(request)
    user_sub = _extract_user_sub(request)
    try:
        limiter.check(ip=ip, user_sub=user_sub)
    except RateLimitExceeded as exc:
        raise _build_429(exc) from exc


__all__ = [
    "RateLimiter",
    "RateLimitExceeded",
    "rate_limit_dependency",
]
