"""Bearer-token authentication dependency (ADR-0002).

Resolves the caller's ``TokenPayload`` from the ``Authorization`` header.
Returns ``401 UNAUTHORIZED`` on missing/malformed/expired/invalid tokens,
using the shared error envelope from ``app/models/error.py``.

The dependency raises ``HTTPException`` whose ``detail`` is already shaped
as the canonical ``ErrorResponse`` envelope. The application-wide
exception handler (registered in ``app/main.py``) unwraps it so the wire
response is ``{"error": {...}}`` and not ``{"detail": {"error": ...}}}``.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.jwt import InvalidAppTokenError, decode_app_token
from app.models.auth import TokenPayload
from app.models.error import ErrorBody, ErrorResponse


def _unauthorized(reason: str) -> HTTPException:
    body = ErrorResponse(
        error=ErrorBody(
            code="UNAUTHORIZED",
            message="Authentication required.",
            details={"reason": reason},
        )
    )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=body.model_dump(),
    )


def get_current_user(request: Request) -> TokenPayload:
    """FastAPI dependency: extract and validate the Bearer token from the request.

    Raises ``HTTPException(401)`` on any failure (missing header, wrong scheme,
    malformed JWT, expired JWT, or signature mismatch). Returns a typed
    ``TokenPayload`` on success.
    """
    header = request.headers.get("Authorization")
    if not header:
        raise _unauthorized("missing_bearer_token")

    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _unauthorized("malformed_bearer_token")

    try:
        return decode_app_token(parts[1])
    except InvalidAppTokenError as exc:
        reason = "token_expired" if "expired" in str(exc) else "invalid_token"
        raise _unauthorized(reason) from exc


__all__ = ["get_current_user"]
