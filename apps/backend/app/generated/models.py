# Generated from specs/main.tsp. Do not edit.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Status(StrEnum):
    ok = "ok"


class HealthResponse(BaseModel):
    status: Status
