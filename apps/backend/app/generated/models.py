# Generated from specs/main.tsp. Do not edit.

from __future__ import annotations

from datetime import date as date_aliased
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, conint, constr


class ApiError(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    code: str
    message: str
    fieldErrors: dict[str, str] | None = None


class TimeZone(StrEnum):
    Europe_Moscow = "Europe/Moscow"


class AvailableSlot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    startsAt: AwareDatetime
    endsAt: AwareDatetime


class Status(StrEnum):
    ok = "ok"


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status


class AvailabilityDay(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    date: date_aliased
    slots: list[AvailableSlot]


class Booking(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: UUID
    meetingTypeId: constr(
        pattern=r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", min_length=1, max_length=64
    )
    meetingTypeName: constr(min_length=1, max_length=120) = Field(
        ...,
        description="Однострочный обычный текст; края очищаются от пробелов, длина в Unicode.",
    )
    startsAt: AwareDatetime
    endsAt: AwareDatetime
    durationMinutes: conint(ge=1, le=540)
    timeZone: TimeZone


class BookingRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    meetingTypeId: constr(
        pattern=r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", min_length=1, max_length=64
    )
    startsAt: AwareDatetime = Field(
        ...,
        description="RFC 3339 со смещением или Z; эквивалентные моменты равнозначны.",
    )


class MeetingType(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: constr(
        pattern=r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$", min_length=1, max_length=64
    )
    name: constr(min_length=1, max_length=120) = Field(
        ...,
        description="Однострочный обычный текст; края очищаются от пробелов, длина в Unicode.",
    )
    description: constr(min_length=1, max_length=2000) = Field(
        ...,
        description="Обычный текст с внутренними переносами; края очищаются от пробелов.",
    )
    durationMinutes: conint(ge=1, le=540)


class MeetingTypeList(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    serverTime: AwareDatetime
    items: list[MeetingType]


class UpcomingBookings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    serverTime: AwareDatetime
    items: list[Booking]


class Availability(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    serverTime: AwareDatetime
    timeZone: TimeZone
    windowStartDate: date_aliased
    windowEndDate: date_aliased
    days: list[AvailabilityDay] = Field(..., max_length=14, min_length=14)
