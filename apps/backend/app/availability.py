from datetime import UTC, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from app.clock import calendar_clock
from app.database import connect
from app.generated.models import Availability

router = APIRouter()
MOSCOW = ZoneInfo("Europe/Moscow")


@router.get(
    "/api/meeting-types/{id}/availability",
    response_model=Availability,
    operation_id="getAvailability",
)
def get_availability(
    id: Annotated[
        str,
        Path(
            min_length=1, max_length=64, pattern=r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$"
        ),
    ],
    clock=Depends(calendar_clock),
):
    with connect() as connection:
        meeting_type = connection.execute(
            "SELECT duration_minutes FROM meeting_types WHERE id = %s", (id,)
        ).fetchone()
        if meeting_type is None:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "MEETING_TYPE_NOT_FOUND",
                    "message": "Тип встречи не найден",
                },
            )
        server_time = clock(connection)
        first_date = server_time.astimezone(MOSCOW).date() + timedelta(days=1)
        occupied = connection.execute(
            "SELECT starts_at, ends_at FROM bookings WHERE starts_at < %s AND ends_at > %s",
            (
                datetime.combine(first_date + timedelta(days=14), time(), MOSCOW),
                datetime.combine(first_date, time(), MOSCOW),
            ),
        ).fetchall()
    duration = timedelta(minutes=meeting_type["duration_minutes"])
    days = []
    for offset in range(14):
        date = first_date + timedelta(days=offset)
        start = datetime.combine(date, time(9), MOSCOW)
        closing = datetime.combine(date, time(18), MOSCOW)
        slots = []
        while start + duration <= closing:
            if not any(
                start < busy["ends_at"] and start + duration > busy["starts_at"]
                for busy in occupied
            ):
                slots.append(
                    {
                        "startsAt": start.astimezone(UTC),
                        "endsAt": (start + duration).astimezone(UTC),
                    }
                )
            start += timedelta(minutes=30)
        days.append({"date": date, "slots": slots})
    return {
        "serverTime": server_time.astimezone(UTC),
        "timeZone": "Europe/Moscow",
        "windowStartDate": first_date,
        "windowEndDate": first_date + timedelta(days=13),
        "days": days,
    }
