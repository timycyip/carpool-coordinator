"""Request and response models for session-admin assignment."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminAssignUser(BaseModel):
    """Canonical Google account identity to grant session-admin access."""

    model_config = ConfigDict(extra="forbid")

    sub: str = Field(min_length=1)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AdminAssignRequest(BaseModel):
    """Session-admin assignment request body."""

    model_config = ConfigDict(extra="forbid")

    user: AdminAssignUser


class AdminAssignResponse(BaseModel):
    """Result of assigning a user as a session admin."""

    session_code: str
    user_sub: str
    email: str
    role: Literal["session_admin"] = "session_admin"
    assigned_by_sub: str
    assigned_at: datetime
    already_assigned: bool


__all__ = ["AdminAssignRequest", "AdminAssignResponse", "AdminAssignUser"]
