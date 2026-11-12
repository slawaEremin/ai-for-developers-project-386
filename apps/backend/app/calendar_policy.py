"""Общие окно записи, рабочие часы и сетка стартов владельца."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")
_WINDOW_DAYS = 14
_OPENING = time(9)
_CLOSING = time(18)
_START_STEP = timedelta(minutes=30)


def booking_window(now: datetime) -> tuple[date, date]:
    first = now.astimezone(MOSCOW).date() + timedelta(days=1)
    return first, first + timedelta(days=_WINDOW_DAYS - 1)


def _working_hours(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, _OPENING, MOSCOW), datetime.combine(
        day, _CLOSING, MOSCOW
    )


def slot_intervals(day: date, duration: timedelta):
    start, closing = _working_hours(day)
    while start + duration <= closing:
        yield start, start + duration
        start += _START_STEP


def is_valid_slot(start: datetime, end: datetime) -> bool:
    start = start.astimezone(MOSCOW)
    opening, closing = _working_hours(start.date())
    return opening <= start < end <= closing and (
        start - opening
    ) % _START_STEP == timedelta(0)
