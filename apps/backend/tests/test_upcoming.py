"""Предстоящие записи через HTTP на изолированной настоящей PostgreSQL."""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_meeting_types import PAYLOAD

from app.clock import calendar_clock
from app.main import app

pytestmark = pytest.mark.usefixtures("database")


@pytest.fixture
def owner_client():
    now = [datetime.fromisoformat("2026-11-12T12:00:00+00:00")]
    app.dependency_overrides[calendar_clock] = lambda: lambda connection: now[0]
    try:
        with TestClient(app) as client:
            yield client, now
    finally:
        app.dependency_overrides.pop(calendar_clock, None)


def test_empty_upcoming_has_server_time_and_no_store(owner_client):
    client, _ = owner_client
    response = client.get("/api/bookings/upcoming")
    assert response.status_code == 200
    assert response.json() == {"serverTime": "2026-11-12T12:00:00Z", "items": []}
    assert response.headers["cache-control"] == "no-store"


def create_booking(client, meeting_type, start, key=None):
    response = client.post(
        "/api/bookings",
        json={"meetingTypeId": meeting_type, "startsAt": start},
        headers={"Idempotency-Key": str(key or uuid4())},
    )
    assert response.status_code == 201
    return response.json()


def test_all_types_exact_start_and_history_retains_successful_key(owner_client):
    from app.prepare import prepare_database

    client, now = owner_client
    for id, duration in [("first", 30), ("second", 45)]:
        assert (
            client.post(
                "/api/meeting-types",
                json={**PAYLOAD, "id": id, "durationMinutes": duration},
            ).status_code
            == 201
        )
    later = create_booking(client, "second", "2026-11-14T08:00:00Z")
    key = uuid4()
    boundary = create_booking(client, "first", "2026-11-14T07:00:00Z", key)
    now[0] = datetime.fromisoformat("2026-11-14T07:00:00+00:00")
    response = client.get("/api/bookings/upcoming")
    assert response.json() == {
        "serverTime": "2026-11-14T07:00:00Z",
        "items": [boundary, later],
    }
    assert later == {
        "id": later["id"],
        "meetingTypeId": "second",
        "meetingTypeName": PAYLOAD["name"],
        "startsAt": "2026-11-14T08:00:00Z",
        "endsAt": "2026-11-14T08:45:00Z",
        "durationMinutes": 45,
        "timeZone": "Europe/Moscow",
    }
    # Уже начавшаяся запись исключается, хотя до её конца ещё почти 30 минут.
    now[0] = datetime.fromisoformat("2026-11-14T07:00:00.000001+00:00")
    assert client.get("/api/bookings/upcoming").json()["items"] == [later]
    now[0] = datetime.fromisoformat("2027-01-01T12:00:00+00:00")
    prepare_database()
    assert client.get("/api/bookings/upcoming").json()["items"] == []
    replay = client.post(
        "/api/bookings",
        json={"meetingTypeId": "first", "startsAt": "2026-11-14T10:00:00+03:00"},
        headers={"Idempotency-Key": str(key)},
    )
    assert replay.status_code == 200
    assert replay.json() == boundary


def test_upcoming_does_not_limit_saved_bookings_to_guest_window(owner_client):
    client, now = owner_client
    client.post("/api/meeting-types", json=PAYLOAD)
    now[0] = datetime.fromisoformat("2027-01-01T12:00:00+00:00")
    distant = create_booking(client, PAYLOAD["id"], "2027-01-03T07:00:00Z")
    now[0] = datetime.fromisoformat("2026-11-12T12:00:00+00:00")
    near = create_booking(client, PAYLOAD["id"], "2026-11-14T07:00:00Z")
    assert client.get("/api/bookings/upcoming").json()["items"] == [near, distant]
