"""Публичная доступность, управляемое время и настоящая PostgreSQL."""

from datetime import datetime
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_meeting_types import PAYLOAD

from app.clock import calendar_clock
from app.main import app

pytestmark = pytest.mark.usefixtures("database")


def test_availability_contains_all_fourteen_moscow_dates_and_full_slots():
    with TestClient(app) as client:
        assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 201
        result = client.get("/api/meeting-types/consultation/availability")
        assert result.status_code == 200
        body = result.json()
        assert len(body["days"]) == 14
        assert body["timeZone"] == "Europe/Moscow"
        assert body["serverTime"].endswith("Z")
        assert result.headers["cache-control"] == "no-store"


@pytest.fixture
def fixed_clock():
    current = [datetime.fromisoformat("2026-11-12T21:00:00+00:00")]
    app.dependency_overrides[calendar_clock] = lambda: lambda connection: current[0]
    try:
        yield current
    finally:
        app.dependency_overrides.pop(calendar_clock, None)


@pytest.mark.parametrize(
    ("duration", "count", "last_start", "last_end"),
    [
        (1, 18, "14:30:00Z", "14:31:00Z"),
        (30, 18, "14:30:00Z", "15:00:00Z"),
        (45, 17, "14:00:00Z", "14:45:00Z"),
        (540, 1, "06:00:00Z", "15:00:00Z"),
    ],
)
def test_window_uses_moscow_midnight_and_unrounded_duration(
    fixed_clock, duration, count, last_start, last_end
):
    with TestClient(app) as client:
        client.post("/api/meeting-types", json={**PAYLOAD, "durationMinutes": duration})
        body = client.get("/api/meeting-types/consultation/availability").json()
        assert body["serverTime"] == "2026-11-12T21:00:00Z"
        assert body["windowStartDate"] == "2026-11-14"
        assert body["windowEndDate"] == "2026-11-27"
        assert body["days"][0]["date"] == "2026-11-14"
        assert body["days"][-1]["date"] == "2026-11-27"
        for day in body["days"]:
            assert len(day["slots"]) == count
            assert day["slots"][0]["startsAt"] == day["date"] + "T06:00:00Z"
            assert day["slots"][-1] == {
                "startsAt": day["date"] + "T" + last_start,
                "endsAt": day["date"] + "T" + last_end,
            }
        fixed_clock[0] = datetime.fromisoformat("2026-11-12T20:59:59+00:00")
        before = client.get("/api/meeting-types/consultation/availability").json()
        assert before["windowStartDate"] == "2026-11-13"
        assert before["windowEndDate"] == "2026-11-26"


def test_shared_occupancy_removes_partial_exact_and_nested_intervals_but_allows_touching(
    database, fixed_clock
):
    with TestClient(app) as client:
        client.post("/api/meeting-types", json={**PAYLOAD, "durationMinutes": 45})
        client.post(
            "/api/meeting-types", json={**PAYLOAD, "id": "other", "durationMinutes": 90}
        )
        with psycopg.connect(database) as connection:
            connection.execute(
                "INSERT INTO bookings (id, owner_id, meeting_type_id, meeting_type_name, duration_minutes, starts_at, ends_at) VALUES (%s, 1, 'other', 'Другой', 90, '2026-11-14T07:00Z', '2026-11-14T08:30Z')",
                (uuid4(),),
            )
            connection.execute(
                "INSERT INTO bookings (id, owner_id, meeting_type_id, meeting_type_name, duration_minutes, starts_at, ends_at) VALUES (%s, 1, 'other', 'Другой', 540, '2026-11-15T06:00Z', '2026-11-15T15:00Z')",
                (uuid4(),),
            )
        body = client.get("/api/meeting-types/consultation/availability").json()
        starts = [slot["startsAt"] for slot in body["days"][0]["slots"]]
        assert starts[:2] == ["2026-11-14T06:00:00Z", "2026-11-14T08:30:00Z"]
        assert "2026-11-14T06:30:00Z" not in starts
        assert "2026-11-14T07:00:00Z" not in starts
        assert "2026-11-14T07:30:00Z" not in starts
        assert "2026-11-14T08:00:00Z" not in starts
        assert body["days"][1] == {"date": "2026-11-15", "slots": []}
        assert len(body["days"]) == 14
        other = client.get("/api/meeting-types/other/availability").json()
        assert other["days"][0]["slots"][0]["startsAt"] == "2026-11-14T08:30:00Z"
        assert all(
            slot["startsAt"] != "2026-11-14T07:00:00Z"
            for slot in other["days"][0]["slots"]
        )


@pytest.mark.parametrize(
    ("id", "status", "code"),
    [("Missing", 422, "VALIDATION_ERROR"), ("missing", 404, "MEETING_TYPE_NOT_FOUND")],
)
def test_availability_errors_preserve_contract(id, status, code):
    with TestClient(app) as client:
        result = client.get(f"/api/meeting-types/{id}/availability")
        assert result.status_code == status
        assert result.json()["code"] == code
        assert result.headers["cache-control"] == "no-store"


def test_unavailable_database_is_not_an_empty_window(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://calendar:calendar@127.0.0.1:1/calendar?connect_timeout=1",
    )
    with TestClient(app) as client:
        result = client.get("/api/meeting-types/consultation/availability")
        assert result.status_code == 503
        assert result.json()["code"] == "SERVICE_UNAVAILABLE"
        assert result.headers["cache-control"] == "no-store"
