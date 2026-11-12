# Generated from specs/main.tsp. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, conint, constr


class ApiError(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    code: str
    message: str
    fieldErrors: dict[str, str] | None = None


class Status(StrEnum):
    ok = "ok"


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    status: Status


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
