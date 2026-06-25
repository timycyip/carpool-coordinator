"""Audit log Pydantic models and paginated response envelope.

Implements the response shapes for `GET /audit` (FR-11, API contracts §3.16)
and the generic ``PaginatedResponse[T]`` envelope used by all paginated
list endpoints (API contracts §1.5, §4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class AuditEvent(BaseModel):
    """One audit-log entry written by the middleware.

    Stored attributes mirror the ERD §2.6 schema (actor_sub / event_type /
    session_code / ip_address / details) plus the immutable event_id and
    ISO-8601 timestamp. Per NFR-SEC-7, ``details`` carries no PII — only
    actor_sub identifies a user.
    """

    event_id: str
    timestamp: datetime
    actor_sub: str | None = None
    event_type: str
    session_code: str | None = None
    ip_address: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class PaginatedResponse(BaseModel, Generic[T]):
    """Cursor-paginated list response envelope.

    Conforms to API contracts §1.5: ``items``, opaque ``next_cursor``,
    echoed ``limit``. ``next_cursor`` is ``None`` on the final page.
    """

    items: list[T]
    next_cursor: str | None = None
    limit: int
