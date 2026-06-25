"""Authentication request/response models (mirrors `docs/api_contracts.md` §4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GoogleAuthRequest(BaseModel):
    """Body of ``POST /auth/google``. Carries a Google-issued ID token."""

    id_token: str = Field(min_length=1)


class UserInfo(BaseModel):
    """Authenticated user info returned to clients (API contract §5)."""

    sub: str
    email: str
    name: str
    global_role: Literal["superuser", "manager", "none"] = "none"


class GoogleAuthResponse(BaseModel):
    """Success response of ``POST /auth/google`` (API contract §3.1)."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    user: UserInfo


class TokenPayload(BaseModel):
    """Decoded claims from an app session JWT (ADR-0002).

    Used as the dependency output of ``get_current_user`` so route handlers
    receive a typed representation of the caller's identity and role.
    """

    sub: str
    email: str
    name: str
    global_role: str
    exp: int


class GoogleUser(BaseModel):
    """Internal model: the canonical fields extracted from a verified Google ID token."""

    sub: str
    email: str
    name: str


__all__ = [
    "GoogleAuthRequest",
    "GoogleAuthResponse",
    "GoogleUser",
    "TokenPayload",
    "UserInfo",
]
