"""App session JWT issuance and decoding (ADR-0002).

Issues HS256-signed JWTs containing the authenticated user's identity and
global role. Tokens are short-lived (1 hour) and stored in-memory on the
client (never localStorage). Decoding verifies signature and expiry.
"""

from __future__ import annotations

import os
import time
from typing import Any

import jwt

from app.models.auth import GoogleUser, TokenPayload

_TTL_SECONDS = 3600
_ALGORITHM = "HS256"


class InvalidAppTokenError(Exception):
    """Raised when an app session JWT is missing, malformed, expired, or invalid."""


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise InvalidAppTokenError("Server is missing JWT_SECRET configuration")
    return secret


def create_app_token(user: GoogleUser, global_role: str = "none") -> str:
    """Sign and return a 1-hour app session JWT for the given user.

    Claims (per ADR-0002):
      - sub, email, name: from GoogleUser.
      - global_role: one of "superuser" | "manager" | "none".
      - iat, exp: issued-at and now+3600s.
    """
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": user.sub,
        "email": user.email,
        "name": user.name,
        "global_role": global_role,
        "iat": now,
        "exp": now + _TTL_SECONDS,
    }
    return jwt.encode(claims, _secret(), algorithm=_ALGORITHM)


def decode_app_token(token: str) -> TokenPayload:
    """Verify signature + expiry of an app session JWT and return the payload.

    Raises InvalidAppTokenError on any failure.
    """
    if not isinstance(token, str) or not token:
        raise InvalidAppTokenError("Token is empty")
    try:
        claims = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAppTokenError("Token has expired") from exc
    except jwt.InvalidSignatureError as exc:
        raise InvalidAppTokenError("Token signature is invalid") from exc
    except jwt.PyJWTError as exc:
        raise InvalidAppTokenError("Token is malformed") from exc

    required = ("sub", "email", "name", "global_role", "exp")
    missing = [field for field in required if field not in claims]
    if missing:
        raise InvalidAppTokenError(f"Token missing required claims: {missing}")

    return TokenPayload(
        sub=str(claims["sub"]),
        email=str(claims["email"]),
        name=str(claims["name"]),
        global_role=str(claims["global_role"]),
        exp=int(claims["exp"]),
    )


__all__ = ["InvalidAppTokenError", "create_app_token", "decode_app_token"]
