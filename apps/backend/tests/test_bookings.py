"""Запись через HTTP и ограничения настоящей PostgreSQL."""

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_meeting_types import PAYLOAD

from app.clock import calendar_clock
from app.main import app

pytestmark = pytest.mark.usefixtures("database")
REQUEST = {"meetingTypeId": "consultation", "startsAt": "2026-11-14T07:00:00Z"}


@pytest.fixture
def booking_client():
    now = [datetime.fromisoformat("2026-11-12T12:00:00+00:00")]
    app.dependency_overrides[calendar_clock] = lambda: lambda connection: now[0]
    try:
        with TestClient(app) as client:
            assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 201
            yield client, now
    finally:
        app.dependency_overrides.pop(calendar_clock, None)


def post(client, body=None, key=None):
    return client.post(
        "/api/bookings",
        json=REQUEST if body is None else body,
        headers={"Idempotency-Key": str(uuid4()) if key is None else key},
    )


def test_confirm_booking_and_late_equivalent_replay(booking_client):
    client, now = booking_client
    key = str(uuid4())
    result = post(client, key=key)
    assert result.status_code == 201
    body = result.json()
    assert body == {
        "id": body["id"],
        "meetingTypeId": "consultation",
        "meetingTypeName": PAYLOAD["name"],
        "startsAt": "2026-11-14T07:00:00Z",
        "endsAt": "2026-11-14T07:30:00Z",
        "durationMinutes": 30,
        "timeZone": "Europe/Moscow",
    }
    assert result.headers["cache-control"] == "no-store"
    now[0] = datetime.fromisoformat("2027-01-01T12:00:00+00:00")
    replay = post(client, {**REQUEST, "startsAt": "2026-11-14T10:00:00+03:00"}, key)
    assert replay.status_code == 200
    assert replay.json() == body
    mismatch = post(client, {**REQUEST, "startsAt": "2026-11-14T08:00:00Z"}, key)
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1794639600,
        "1794639600",
        "2026-11-14T07:00:00",
        "2026-11-14",
        "2026-11-14 07:00:00Z",
        "2026-11-14T07:00:00+99:00",
    ],
)
def test_start_requires_rfc3339_string_with_zone(booking_client, value):
    client, _ = booking_client
    result = post(client, {**REQUEST, "startsAt": value})
    assert result.status_code == 422
    assert result.json()["code"] == "VALIDATION_ERROR"
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("key", ["bad", "", "d2719fdf78ec4f569cbc1b6c115fc517"])
def test_key_requires_uuid_header(booking_client, key):
    result = post(booking_client[0], key=key)
    assert result.status_code == 422
    assert result.json()["code"] == "VALIDATION_ERROR"


def test_missing_key_extra_fields_json_and_content_type(booking_client):
    client, _ = booking_client
    assert client.post("/api/bookings", json=REQUEST).status_code == 422
    assert (
        post(client, {**REQUEST, "endsAt": "2026-11-14T08:00:00Z"}).status_code == 422
    )
    result = client.post(
        "/api/bookings", content="{", headers={"content-type": "application/json"}
    )
    assert result.status_code == 400
    assert result.json()["code"] == "BAD_REQUEST"
    result = client.post("/api/bookings", content="{}")
    assert result.status_code == 415
    assert result.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


@pytest.mark.parametrize(
    ("start", "status", "code"),
    [
        ("2026-11-12T07:00:00Z", 422, "OUTSIDE_BOOKING_WINDOW"),
        ("2026-11-27T07:00:00Z", 422, "OUTSIDE_BOOKING_WINDOW"),
        ("2026-11-13T05:30:00Z", 422, "INVALID_SLOT"),
        ("2026-11-13T07:15:00Z", 422, "INVALID_SLOT"),
        ("2026-11-13T07:00:01Z", 422, "INVALID_SLOT"),
        ("2026-11-13T07:00:00.1Z", 422, "INVALID_SLOT"),
        ("2026-11-13T15:00:00Z", 422, "INVALID_SLOT"),
        ("2026-11-13T06:00:00Z", 201, None),
        ("2026-11-26T14:30:00Z", 201, None),
    ],
)
def test_window_hours_and_start_grid(booking_client, start, status, code):
    result = post(booking_client[0], {**REQUEST, "startsAt": start})
    assert result.status_code == status
    if code:
        assert result.json()["code"] == code


def test_unknown_type_and_refusal_do_not_reserve_key(booking_client):
    client, _ = booking_client
    key = str(uuid4())
    missing = post(client, {**REQUEST, "meetingTypeId": "missing"}, key)
    assert missing.status_code == 404
    assert missing.json()["code"] == "MEETING_TYPE_NOT_FOUND"
    assert post(client, key=key).status_code == 201
    refused = str(uuid4())
    assert post(client, key=refused).json()["code"] == "SLOT_CONFLICT"
    assert (
        post(
            client, {**REQUEST, "startsAt": "2026-11-14T08:00:00Z"}, refused
        ).status_code
        == 201
    )


@pytest.mark.parametrize(
    ("first_duration", "second_duration", "second_start", "status"),
    [
        (90, 30, "07:30", 409),
        (30, 90, "06:30", 409),
        (60, 60, "07:30", 409),
        (60, 30, "08:00", 201),
        (45, 45, "14:30", 422),
        (45, 45, "14:00", 201),
    ],
)
def test_global_partial_nested_touching_and_actual_duration(
    booking_client, first_duration, second_duration, second_start, status
):
    client, _ = booking_client
    client.post(
        "/api/meeting-types",
        json={**PAYLOAD, "id": "first", "durationMinutes": first_duration},
    )
    client.post(
        "/api/meeting-types",
        json={**PAYLOAD, "id": "second", "durationMinutes": second_duration},
    )
    assert (
        post(
            client, {"meetingTypeId": "first", "startsAt": "2026-11-14T07:00:00Z"}
        ).status_code
        == 201
    )
    result = post(
        client,
        {"meetingTypeId": "second", "startsAt": f"2026-11-14T{second_start}:00Z"},
    )
    assert result.status_code == status
    if status == 409:
        assert result.json() == {
            "code": "SLOT_CONFLICT",
            "message": "Это время уже занято. Выберите другой слот",
        }


def counts(database):
    import psycopg

    with psycopg.connect(database) as connection:
        return connection.execute(
            "SELECT (SELECT count(*) FROM bookings), (SELECT count(*) FROM booking_keys)"
        ).fetchone()


def wait_blocked(database, holder, expected):
    import time
    from threading import Event

    import psycopg

    deadline = time.monotonic() + 5
    with psycopg.connect(database, autocommit=True) as observer:
        while time.monotonic() < deadline:
            count = observer.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE %s = ANY(pg_blocking_pids(pid))",
                (holder.info.backend_pid,),
            ).fetchone()[0]
            if count >= expected:
                return
            Event().wait(0.01)
    pytest.fail("HTTP requests did not reach the managed owner lock")


@pytest.mark.parametrize("scenario", ["overlap", "same", "different-payload", "touch"])
def test_concurrent_http_requests_use_fresh_key_snapshot(
    database, booking_client, scenario
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    import psycopg

    client, _ = booking_client
    first_key, second_key = str(uuid4()), str(uuid4())
    second = REQUEST.copy()
    if scenario in ("same", "different-payload"):
        second_key = first_key
    if scenario in ("touch", "different-payload"):
        second["startsAt"] = "2026-11-14T07:30:00Z"
    if scenario == "same":
        second["startsAt"] = "2026-11-14T10:00:00+03:00"
    barrier = Barrier(3)

    def send(body, key):
        barrier.wait(timeout=5)
        return post(client, body, key)

    with (
        psycopg.connect(database) as holder,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        holder.execute("SELECT id FROM owners WHERE id = 1 FOR UPDATE")
        first = executor.submit(send, REQUEST, first_key)
        other = executor.submit(send, second, second_key)
        barrier.wait(timeout=5)
        # Оба запроса действительно ждут: второй может ждать через первого.
        import time

        deadline = time.monotonic() + 5
        with psycopg.connect(database, autocommit=True) as observer:
            while time.monotonic() < deadline:
                waiting = observer.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0 AND query LIKE 'SELECT id FROM owners%%'"
                ).fetchone()[0]
                if waiting >= 2:
                    break
                from threading import Event

                Event().wait(0.01)
            else:
                pytest.fail("Both requests must reach row locks")
        holder.commit()
        results = [first.result(timeout=5), other.result(timeout=5)]
    statuses = sorted(result.status_code for result in results)
    if scenario == "same":
        assert statuses == [200, 201]
        assert results[0].json() == results[1].json()
    elif scenario == "touch":
        assert statuses == [201, 201]
    else:
        assert statuses == [201, 409]
        assert next(
            result.json()["code"] for result in results if result.status_code == 409
        ) == (
            "IDEMPOTENCY_KEY_REUSED"
            if scenario == "different-payload"
            else "SLOT_CONFLICT"
        )
    assert counts(database) == ((2, 2) if scenario == "touch" else (1, 1))


def test_clock_is_read_after_waiting_through_moscow_midnight(database, booking_client):
    from concurrent.futures import ThreadPoolExecutor

    import psycopg

    client, now = booking_client
    now[0] = datetime.fromisoformat("2026-11-12T20:59:59+00:00")
    with (
        psycopg.connect(database) as holder,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        holder.execute("SELECT id FROM owners WHERE id = 1 FOR UPDATE")
        future = executor.submit(
            post, client, {**REQUEST, "startsAt": "2026-11-13T07:00:00Z"}
        )
        wait_blocked(database, holder, 1)
        now[0] = datetime.fromisoformat("2026-11-12T21:00:00+00:00")
        holder.commit()
        result = future.result(timeout=5)
    assert result.status_code == 422
    assert result.json()["code"] == "OUTSIDE_BOOKING_WINDOW"
    assert counts(database) == (0, 0)


def test_window_checked_before_midnight_can_commit_after_it(database, booking_client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    client, now = booking_client
    now[0] = datetime.fromisoformat("2026-11-12T20:59:59+00:00")
    checked, proceed = Event(), Event()
    calls = []

    def clock(connection):
        captured = now[0]
        calls.append(captured)
        checked.set()
        assert proceed.wait(5)
        return captured

    app.dependency_overrides[calendar_clock] = lambda: clock
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            post, client, {**REQUEST, "startsAt": "2026-11-13T07:00:00Z"}
        )
        try:
            assert checked.wait(5)
            now[0] = datetime.fromisoformat("2026-11-12T21:00:00+00:00")
        finally:
            proceed.set()
        result = future.result(timeout=5)
    assert result.status_code == 201
    assert len(calls) == 1
    assert counts(database) == (1, 1)


def test_database_failure_rolls_back_booking_and_key_then_key_can_succeed(
    database, booking_client
):
    import psycopg

    client, _ = booking_client
    key = str(uuid4())
    with psycopg.connect(database) as connection:
        connection.execute(
            "CREATE FUNCTION fail_key() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected failure'; END $$"
        )
        connection.execute(
            "CREATE TRIGGER fail_key BEFORE INSERT ON booking_keys FOR EACH ROW EXECUTE FUNCTION fail_key()"
        )
    result = post(client, key=key)
    assert result.status_code == 503
    assert result.json()["code"] == "SERVICE_UNAVAILABLE"
    assert counts(database) == (0, 0)
    with psycopg.connect(database) as connection:
        connection.execute("DROP TRIGGER fail_key ON booking_keys")
    assert post(client, key=key).status_code == 201
    assert counts(database) == (1, 1)


def test_raw_database_constraints_forbid_overlap_and_duplicate_successful_key(
    database, booking_client
):
    import psycopg
    from psycopg.errors import ExclusionViolation, UniqueViolation

    client, _ = booking_client
    key = str(uuid4())
    assert post(client, key=key).status_code == 201
    client.post("/api/meeting-types", json={**PAYLOAD, "id": "other"})
    statement = "INSERT INTO bookings (id, owner_id, meeting_type_id, meeting_type_name, duration_minutes, starts_at, ends_at) VALUES (%s, 1, 'other', 'Другой', 30, %s, %s)"
    with pytest.raises(ExclusionViolation), psycopg.connect(database) as connection:
        connection.execute(
            statement, (uuid4(), "2026-11-14T07:00Z", "2026-11-14T07:30Z")
        )
    with pytest.raises(UniqueViolation), psycopg.connect(database) as connection:
        booking_id = uuid4()
        connection.execute(
            statement, (booking_id, "2026-11-14T07:30Z", "2026-11-14T08:00Z")
        )
        connection.execute(
            "INSERT INTO booking_keys VALUES (%s, %s)", (key, booking_id)
        )
    assert counts(database) == (1, 1)


def test_successful_key_survives_preparation_and_other_type_cannot_reuse_it(
    booking_client,
):
    from app.prepare import prepare_database

    client, _ = booking_client
    key = str(uuid4())
    original = post(client, key=key)
    prepare_database()
    client.post("/api/meeting-types", json={**PAYLOAD, "id": "other"})
    different = post(client, {**REQUEST, "meetingTypeId": "other"}, key)
    assert different.status_code == 409
    assert different.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    def unavailable_clock(connection):
        raise AssertionError("Successful replay must not consult moving clock")

    app.dependency_overrides[calendar_clock] = lambda: unavailable_clock
    repeated = post(client, key=key)
    assert repeated.status_code == 200
    assert repeated.json() == original.json()
