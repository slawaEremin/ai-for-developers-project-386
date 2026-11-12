"""Подтверждение записи: одна транзакция, общая блокировка и успешный ключ."""

import re
from datetime import UTC, timedelta
from time import monotonic
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from psycopg import IsolationLevel
from psycopg.errors import DeadlockDetected, ExclusionViolation, SerializationFailure
from pydantic import field_validator

from app.availability import MOSCOW
from app.clock import calendar_clock
from app.database import connect
from app.generated.models import Booking, BookingRequest

router = APIRouter()


class CreateBooking(BookingRequest):
    @field_validator("startsAt", mode="before")
    @classmethod
    def explicit_timezone(cls, value):
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
        ):
            raise ValueError("Укажите RFC 3339 с часовым поясом")
        return value


class BookingRefusal(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def booking_object(row):
    return Booking(
        id=row["id"],
        meetingTypeId=row["meeting_type_id"],
        meetingTypeName=row["meeting_type_name"],
        startsAt=row["starts_at"].astimezone(UTC),
        endsAt=row["ends_at"].astimezone(UTC),
        durationMinutes=row["duration_minutes"],
        timeZone="Europe/Moscow",
    )


def create_booking_transaction(connection, body, key, clock):
    # Отдельные statements важны: после ожидания Read Committed видит новый ключ.
    connection.execute("SELECT id FROM owners WHERE id = 1 FOR UPDATE").fetchone()
    previous = connection.execute(
        "SELECT b.* FROM booking_keys k JOIN bookings b ON b.id = k.booking_id "
        "WHERE k.key = %s",
        (key,),
    ).fetchone()
    if previous:
        if (
            previous["meeting_type_id"] != body.meetingTypeId
            or previous["starts_at"] != body.startsAt
        ):
            raise BookingRefusal(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "Ключ попытки уже использован с другими данными",
            )
        return booking_object(previous), False
    now = clock(connection)
    meeting_type = connection.execute(
        "SELECT * FROM meeting_types WHERE id = %s", (body.meetingTypeId,)
    ).fetchone()
    if not meeting_type:
        raise BookingRefusal(404, "MEETING_TYPE_NOT_FOUND", "Тип встречи не найден")
    start = body.startsAt.astimezone(MOSCOW)
    end = start + timedelta(minutes=meeting_type["duration_minutes"])
    tomorrow = now.astimezone(MOSCOW).date() + timedelta(days=1)
    if not tomorrow <= start.date() <= tomorrow + timedelta(days=13):
        raise BookingRefusal(
            422, "OUTSIDE_BOOKING_WINDOW", "Время вне окна записи. Выберите другой слот"
        )
    if (
        start.hour < 9
        or start.minute not in (0, 30)
        or start.second
        or start.microsecond
        or end.date() != start.date()
        or (end.hour, end.minute, end.second, end.microsecond) > (18, 0, 0, 0)
    ):
        raise BookingRefusal(
            422, "INVALID_SLOT", "Выберите время по сетке и в рабочие часы"
        )
    occupied = connection.execute(
        "SELECT id FROM bookings WHERE starts_at < %s AND ends_at > %s LIMIT 1",
        (end, start),
    ).fetchone()
    if occupied:
        raise BookingRefusal(
            409, "SLOT_CONFLICT", "Это время уже занято. Выберите другой слот"
        )
    row = connection.execute(
        "INSERT INTO bookings (id, owner_id, meeting_type_id, meeting_type_name, duration_minutes, starts_at, ends_at) "
        "VALUES (%s, 1, %s, %s, %s, %s, %s) RETURNING *",
        (
            uuid4(),
            body.meetingTypeId,
            meeting_type["name"],
            meeting_type["duration_minutes"],
            start,
            end,
        ),
    ).fetchone()
    connection.execute(
        "INSERT INTO booking_keys (key, booking_id) VALUES (%s, %s)", (key, row["id"])
    )
    return booking_object(row), True


@router.post("/api/bookings", response_model=Booking, operation_id="createBooking")
def create_booking(
    body: CreateBooking,
    response: Response,
    idempotency_key: Annotated[
        str,
        Header(
            pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ],
    clock=Depends(calendar_clock),
):
    deadline = monotonic() + 10
    try:
        for execution in range(3):
            try:
                with connect(deadline=deadline) as connection:
                    connection.isolation_level = IsolationLevel.READ_COMMITTED
                    booking, created = create_booking_transaction(
                        connection, body, UUID(idempotency_key), clock
                    )
                break
            except (DeadlockDetected, SerializationFailure):
                if execution == 2:
                    raise
        # Выход из context manager завершил COMMIT до отправки успеха.
        response.status_code = 201 if created else 200
        return booking
    except ExclusionViolation as error:
        if error.diag.constraint_name != "bookings_no_overlap":
            raise
        return JSONResponse(
            status_code=409,
            content={
                "code": "SLOT_CONFLICT",
                "message": "Это время уже занято. Выберите другой слот",
            },
        )
    except BookingRefusal as error:
        return JSONResponse(
            status_code=error.status,
            content={"code": error.code, "message": error.message},
        )
