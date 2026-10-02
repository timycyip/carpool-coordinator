"""Audit logging middleware.

Per ADR-0005, audit logging sits between rate_limit (1st) and auth (3rd)
in the middleware chain. Each ``log()`` call is **fire-and-forget** — the
DB write is scheduled with ``asyncio.create_task`` and failures are
captured to stderr (CloudWatch in production) so they never block or
break the calling request.

Per FR-11 and NFR-SEC-7, ``details`` carries no PII. The only user
identifier written is ``actor_sub`` (the Google subject). Email and
display name must never appear in audit records.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import Depends, Request

from app.config import app_data_table_name
from app.db import get_ddb_client
from app.repositories.audit import AuditRepository

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient


EVENT_AUTH_LOGIN_SUCCESS = "auth.login.success"
EVENT_AUTH_LOGIN_FAILURE = "auth.login.failure"
EVENT_SESSION_CREATED = "session.created"
EVENT_SESSION_UPDATED = "session.updated"
EVENT_SESSION_DELETED = "session.deleted"
EVENT_SESSION_ADMIN_ASSIGN = "session_admin.assign"
EVENT_RBAC_DENIED = "rbac.denied"


def _extract_ip(request: Request) -> str:
    """Resolve the client IP from the edge or the direct socket."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


class AuditLogger:
    """Writes audit events to the ``AUDIT#<date>`` partition of ``app_data``.

    The constructor accepts a low-level boto3 DynamoDB client so the
    middleware can be instantiated in tests with a moto-mocked client
    (see ``tests/conftest.py::ddb_client``).
    """

    def __init__(self, client: DynamoDBClient, table_name: str | None = None) -> None:
        resolved_table_name = table_name or app_data_table_name()
        self._repo = AuditRepository(table_name=resolved_table_name, client=client)
        self._pending: set[asyncio.Task[None]] = set()

    async def log(
        self,
        event_type: str,
        actor_sub: str | None,
        session_code: str | None,
        details: dict[str, Any],
        request: Request,
    ) -> None:
        """Schedule a non-blocking audit write.

        Generates ``event_id`` (UUIDv4) and the ISO-8601 timestamp up
        front so the same identifiers are visible to the caller (useful
        for log correlation) and embedded in the stored item. The actual
        ``PutItem`` runs in a background task; exceptions are swallowed
        and reported to stderr so the calling request is never affected.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        ip_address = _extract_ip(request)
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
        task = asyncio.create_task(self._safe_write(date_str, event_id, attrs))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _safe_write(
        self, date_str: str, event_id: str, attrs: dict[str, Any]
    ) -> None:
        try:
            await self._repo.write(date_str, event_id, attrs)
        except Exception as exc:  # noqa: BLE001 — fire-and-forget; never raise
            print(
                f"audit write failed: event_id={event_id} error={exc!r}",
                file=sys.stderr,
            )

    async def drain(self) -> None:
        """Await all pending writes (used by tests for deterministic flush)."""
        if not self._pending:
            return
        await asyncio.gather(*self._pending, return_exceptions=True)


def audit_dependency(
    request: Request,
    client: DynamoDBClient = Depends(get_ddb_client),
) -> AuditLogger:
    """FastAPI dependency returning an :class:`AuditLogger` for this request.

    Stores the logger in ``request.state.audit_logger`` so callers (and
    tests) can await ``drain()`` for deterministic flush of pending writes.
    """
    logger = AuditLogger(client=client)
    request.state.audit_logger = logger
    return logger
