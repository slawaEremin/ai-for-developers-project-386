import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from psycopg.errors import UniqueViolation
from pydantic import field_validator

from app.database import connect
from app.generated.models import MeetingType

router = APIRouter()


class CreateMeetingType(MeetingType):
    @field_validator("name", "description", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def single_line_name(cls, value):
        if re.search(r"[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]", value):
            raise ValueError("Название должно быть однострочным")
        return value

    @field_validator("durationMinutes", mode="before")
    @classmethod
    def numeric_integer(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Укажите целое число от 1 до 540")
        return value


@router.post(
    "/api/meeting-types",
    status_code=201,
    response_model=MeetingType,
    operation_id="createMeetingType",
)
def create_meeting_type(body: CreateMeetingType):
    try:
        with connect() as connection:
            connection.execute(
                "INSERT INTO meeting_types "
                "(id, owner_id, name, description, duration_minutes) "
                "VALUES (%s, 1, %s, %s, %s)",
                (body.id, body.name, body.description, body.durationMinutes),
            )
    except UniqueViolation:
        return JSONResponse(
            status_code=409,
            content={
                "code": "MEETING_TYPE_ID_CONFLICT",
                "message": "Тип встречи с таким id уже существует",
                "fieldErrors": {"id": "Этот id уже занят"},
            },
        )
    return body
