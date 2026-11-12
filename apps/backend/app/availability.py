from datetime import UTC, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from app.calendar_policy import MOSCOW, booking_window, slot_intervals
from app.clock import calendar_clock
from app.database import connect
from app.generated.models import Availability

router = APIRouter()


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
        first_date, last_date = booking_window(server_time)
        occupied = connection.execute(
            "SELECT starts_at, ends_at FROM bookings WHERE starts_at < %s AND ends_at > %s",
            (
                datetime.combine(last_date + timedelta(days=1), time(), MOSCOW),
                datetime.combine(first_date, time(), MOSCOW),
            ),
        ).fetchall()
    duration = timedelta(minutes=meeting_type["duration_minutes"])
    days = []
    date = first_date
    while date <= last_date:
        slots = []
        for start, end in slot_intervals(date, duration):
            if not any(
                start < busy["ends_at"] and end > busy["starts_at"] for busy in occupied
            ):
                slots.append(
                    {"startsAt": start.astimezone(UTC), "endsAt": end.astimezone(UTC)}
                )
        days.append({"date": date, "slots": slots})
        date += timedelta(days=1)
    return {
        "serverTime": server_time.astimezone(UTC),
        "timeZone": "Europe/Moscow",
        "windowStartDate": first_date,
        "windowEndDate": last_date,
        "days": days,
    }
