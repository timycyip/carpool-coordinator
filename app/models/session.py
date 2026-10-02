"""Session request and response models (API contracts §4)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionStatus(StrEnum):
    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    MATCHING_PENDING = "matching_pending"
    MATCHING_PROPOSED = "matching_proposed"
    APPROVED = "approved"
    CLOSED = "closed"


class TripMode(StrEnum):
    TO_DESTINATION = "to_destination"
    FROM_ORIGIN = "from_origin"


class AnchorLocation(BaseModel):
    lat: float
    lon: float
    source: Literal["nominatim"]
    cached_at: datetime


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    trip_mode: TripMode
    anchor_postal_code: str = Field(min_length=1, max_length=20)
    earliest_pickup: datetime
    latest_arrival: datetime
    registration_deadline: datetime
    capacity_hint: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_time_window(self) -> SessionCreate:
        for field_name in (
            "earliest_pickup",
            "latest_arrival",
            "registration_deadline",
        ):
            if getattr(self, field_name).utcoffset() is None:
                raise ValueError(f"{field_name} must include a timezone offset")
        if self.latest_arrival < self.earliest_pickup:
            raise ValueError("latest_arrival must be at or after earliest_pickup")
        if self.registration_deadline > self.earliest_pickup:
            raise ValueError("registration_deadline must be at or before earliest_pickup")
        return self


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    trip_mode: TripMode | None = None
    anchor_postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    earliest_pickup: datetime | None = None
    latest_arrival: datetime | None = None
    registration_deadline: datetime | None = None
    capacity_hint: int | None = Field(default=None, ge=1)
    status: SessionStatus | None = None

    @model_validator(mode="after")
    def validate_explicit_values(self) -> SessionUpdate:
        for field_name in (
            "title",
            "trip_mode",
            "anchor_postal_code",
            "earliest_pickup",
            "latest_arrival",
            "registration_deadline",
            "status",
        ):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        for field_name in (
            "earliest_pickup",
            "latest_arrival",
            "registration_deadline",
        ):
            value = getattr(self, field_name)
            if value is not None and value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a timezone offset")
        return self


class SessionResponse(BaseModel):
    session_code: str
    title: str
    description: str | None = None
    trip_mode: TripMode
    anchor_location: AnchorLocation
    earliest_pickup: datetime
    latest_arrival: datetime
    registration_deadline: datetime
    status: SessionStatus
    created_by_sub: str
    created_at: datetime
    updated_at: datetime
    capacity_hint: int | None = None


__all__ = [
    "AnchorLocation",
    "SessionCreate",
    "SessionResponse",
    "SessionStatus",
    "SessionUpdate",
    "TripMode",
]
