"""Shared error response models.

Implements the error envelope from `docs/api_contracts.md` §2.
Every error response uses `ErrorResponse` — the single consistent
format that all endpoints return on failure.

Status code mapping (§2.1):
  401 UNAUTHORIZED, 403 FORBIDDEN, 404 NOT_FOUND / SESSION_CODE_NOT_FOUND,
  409 REGISTRATION_CLOSED / SESSION_NOT_OPEN / ALREADY_REGISTERED, etc.,
  422 VALIDATION_ERROR, 429 RATE_LIMITED, 500 INTERNAL_ERROR,
  503 SERVICE_UNAVAILABLE.
"""

from pydantic import BaseModel


class ErrorBody(BaseModel):
    """Structured error detail.

    Attributes:
        code: Machine-readable error constant (e.g. ``VALIDATION_ERROR``).
        message: Human-readable, safe to display to end users. No PII,
            no stack traces, no secrets.
        details: Optional structured context (field-level validation
            errors, request IDs for support correlation, etc.).
    """

    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    """Top-level error envelope returned by all endpoints on failure.

    JSON shape: ``{"error": {"code": "...", "message": "...", "details": {...}}}``
    """

    error: ErrorBody
