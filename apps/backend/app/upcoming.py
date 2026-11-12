"""Общий план владельца без ограничения гостевым окном."""

from datetime import UTC

from fastapi import APIRouter, Depends

from app.bookings import booking_object
from app.clock import calendar_clock
from app.database import connect
from app.generated.models import UpcomingBookings

router = APIRouter()


@router.get(
    "/api/bookings/upcoming",
    response_model=UpcomingBookings,
    operation_id="listUpcomingBookings",
)
def list_upcoming_bookings(clock=Depends(calendar_clock)):
    with connect() as connection:
        server_time = clock(connection)
        rows = connection.execute(
            "SELECT * FROM bookings WHERE starts_at >= %s ORDER BY starts_at, id",
            (server_time,),
        ).fetchall()
    return UpcomingBookings(
        serverTime=server_time.astimezone(UTC),
        items=[booking_object(row) for row in rows],
    )
