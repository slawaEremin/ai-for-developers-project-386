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


@pytest.mark.parametrize("sqlstate", ["40P01", "40001"])
@pytest.mark.parametrize("at_commit", [False, True])
def test_transaction_rollback_retries_entire_booking_at_most_three_times(
    database, booking_client, sqlstate, at_commit
):
    import psycopg

    client, _ = booking_client
    with psycopg.connect(database) as connection:
        connection.execute("CREATE SEQUENCE retry_executions")
        connection.execute(
            "CREATE FUNCTION retry_key() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF nextval('retry_executions') < 3 THEN "
            f"RAISE EXCEPTION 'retry rollback' USING ERRCODE = '{sqlstate}'; "
            "END IF; RETURN NEW; END $$"
        )
        connection.execute(
            "CREATE CONSTRAINT TRIGGER retry_key AFTER INSERT ON booking_keys DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION retry_key()"
            if at_commit
            else "CREATE TRIGGER retry_key BEFORE INSERT ON booking_keys FOR EACH ROW EXECUTE FUNCTION retry_key()"
        )
    key = str(uuid4())
    result = post(client, key=key)
    assert result.status_code == 201
    assert post(client, key=key).json() == result.json()
    assert counts(database) == (1, 1)
    with psycopg.connect(database) as connection:
        assert (
            connection.execute("SELECT last_value FROM retry_executions").fetchone()[0]
            == 3
        )


def test_retry_exhaustion_returns_unavailable_after_three_total_executions(
    database, booking_client
):
    import psycopg

    with psycopg.connect(database) as connection:
        connection.execute("CREATE SEQUENCE retry_count")
        connection.execute(
            "CREATE FUNCTION fail_retry() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM nextval('retry_count'); RAISE EXCEPTION 'rollback' USING ERRCODE = '40001'; END $$"
        )
        connection.execute(
            "CREATE TRIGGER fail_retry BEFORE INSERT ON booking_keys FOR EACH ROW EXECUTE FUNCTION fail_retry()"
        )
    response = post(booking_client[0])
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    with psycopg.connect(database) as connection:
        assert (
            connection.execute("SELECT last_value FROM retry_count").fetchone()[0] == 3
        )
    assert counts(database) == (0, 0)


def test_one_ten_second_budget_covers_all_transaction_executions(
    database, booking_client
):
    import time

    import psycopg

    with psycopg.connect(database) as connection:
        connection.execute("CREATE SEQUENCE timed_executions")
        connection.execute(
            "CREATE FUNCTION slow_retry() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM nextval('timed_executions'); PERFORM pg_sleep(4); RAISE EXCEPTION 'rollback' USING ERRCODE = '40001'; END $$"
        )
        connection.execute(
            "CREATE TRIGGER slow_retry BEFORE INSERT ON booking_keys FOR EACH ROW EXECUTE FUNCTION slow_retry()"
        )
    start = time.monotonic()
    response = post(booking_client[0])
    elapsed = time.monotonic() - start
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert 7.5 <= elapsed < 11.5
    assert counts(database) == (0, 0)


def test_owner_lock_wait_is_bounded_by_one_ten_second_budget(database, booking_client):
    import time
    from concurrent.futures import ThreadPoolExecutor

    import psycopg

    with (
        psycopg.connect(database) as holder,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        holder.execute("SELECT id FROM owners WHERE id = 1 FOR UPDATE")
        start = time.monotonic()
        future = executor.submit(post, booking_client[0])
        wait_blocked(database, holder, 1)
        response = future.result(timeout=12)
        assert 9 <= time.monotonic() - start < 11.5
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert counts(database) == (0, 0)


def test_commit_deadline_keeps_unknown_outcome_safe_for_same_key_replay(
    database, booking_client
):
    import time

    import psycopg

    client, _ = booking_client
    with psycopg.connect(database) as connection:
        connection.execute(
            "CREATE FUNCTION slow_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(4); RETURN NEW; END $$"
        )
        connection.execute(
            "CREATE TRIGGER slow_insert BEFORE INSERT ON bookings FOR EACH ROW EXECUTE FUNCTION slow_commit()"
        )
        connection.execute(
            "CREATE CONSTRAINT TRIGGER slow_commit AFTER INSERT ON booking_keys DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION slow_commit()"
        )
        connection.execute(
            "CREATE CONSTRAINT TRIGGER slow_commit2 AFTER INSERT ON booking_keys DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION slow_commit()"
        )
    key = str(uuid4())
    start = time.monotonic()
    response = post(client, key=key)
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert 9 <= time.monotonic() - start < 11.5
    with psycopg.connect(database) as connection:
        connection.execute("DROP TRIGGER slow_insert ON bookings")
        connection.execute("DROP TRIGGER slow_commit ON booking_keys")
        connection.execute("DROP TRIGGER slow_commit2 ON booking_keys")
    result = post(client, key=key)
    # Закрытие сокета при ожидании COMMIT не доказывает rollback.
    assert result.status_code in (200, 201)
    assert post(client, key=key).json() == result.json()
    assert counts(database) == (1, 1)


def test_lost_http_response_after_commit_can_be_replayed_after_restart_and_window_shift(
    database, booking_client
):
    import psycopg

    from app.prepare import prepare_database

    client, now = booking_client
    key = str(uuid4())

    async def lose_response(scope, receive, send):
        async def disconnected(message):
            if message["type"] == "http.response.start":
                raise OSError("transport lost response after commit")
            await send(message)

        await app(scope, receive, disconnected)

    with TestClient(lose_response) as disconnected_client:
        with pytest.raises(OSError):
            post(disconnected_client, key=key)
    assert counts(database) == (1, 1)
    prepare_database()
    now[0] = datetime.fromisoformat("2027-01-01T12:00:00+00:00")
    with TestClient(app) as restarted:
        replay = post(restarted, key=key)
        assert replay.status_code == 200
        assert replay.json()["startsAt"] == REQUEST["startsAt"]
        assert post(restarted, key=key).json() == replay.json()
    assert counts(database) == (1, 1)
    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM bookings").fetchone()[0] == 1


def test_rollback_retry_rechecks_current_window_with_same_key(database, booking_client):
    import psycopg

    client, now = booking_client
    with psycopg.connect(database) as connection:
        connection.execute("CREATE SEQUENCE midnight_retry")
        connection.execute(
            "CREATE FUNCTION fail_once() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF nextval('midnight_retry') = 1 THEN RAISE EXCEPTION 'rollback' USING ERRCODE = '40001'; END IF; RETURN NEW; END $$"
        )
        connection.execute(
            "CREATE TRIGGER fail_once BEFORE INSERT ON booking_keys FOR EACH ROW EXECUTE FUNCTION fail_once()"
        )
    times = iter([now[0], datetime.fromisoformat("2026-11-14T12:00:00+00:00")])
    app.dependency_overrides[calendar_clock] = lambda: lambda connection: next(times)
    key = str(uuid4())
    response = post(client, key=key)
    assert response.status_code == 422
    assert response.json()["code"] == "OUTSIDE_BOOKING_WINDOW"
    assert counts(database) == (0, 0)
    app.dependency_overrides[calendar_clock] = lambda: lambda connection: now[0]
    assert post(client, key=key).status_code == 201
    assert counts(database) == (1, 1)


def test_connection_establishment_and_owner_lock_share_same_deadline(
    database, booking_client, monkeypatch
):
    import select
    import socket
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    client, _ = booking_client
    settings = conninfo_to_dict(database)
    accepted = Event()
    with socket.create_server(("127.0.0.1", 0)) as listener:
        port = listener.getsockname()[1]

        def delayed_connection():
            listener.settimeout(12)
            with listener.accept()[0] as browser:
                accepted.set()
                # Контролируемая задержка именно handshake, затем настоящий PG.
                Event().wait(2)
                with socket.create_connection(
                    (
                        settings.get("host", "127.0.0.1"),
                        int(settings.get("port", 5432)),
                    ),
                    timeout=12,
                ) as postgres:
                    while True:
                        readable, _, _ = select.select([browser, postgres], [], [], 12)
                        if not readable:
                            return
                        for source in readable:
                        try:
                            data = source.recv(65536)
                            if not data:
                                return
                            (postgres if source is browser else browser).sendall(data)
                        except (ConnectionResetError, BrokenPipeError):
                            # После deadline закрытый клиент может прислать TCP RST.
                                return

        monkeypatch.setenv(
            "DATABASE_URL",
            make_conninfo(database, host="127.0.0.1", port=port, sslmode="disable"),
        )
        with (
            psycopg.connect(database) as holder,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            holder.execute("SELECT id FROM owners WHERE id = 1 FOR UPDATE")
            forwarding = executor.submit(delayed_connection)
            started = time.monotonic()
            future = executor.submit(post, client)
            assert accepted.wait(3)
            wait_blocked(database, holder, 1)
            response = future.result(timeout=12)
            elapsed = time.monotonic() - started
            assert 9 <= elapsed < 11.5
            assert response.status_code == 503
            assert response.json()["code"] == "SERVICE_UNAVAILABLE"
            forwarding.result(timeout=3)
    assert counts(database) == (0, 0)


def test_unexpected_failure_returns_internal_error_and_preserves_booking_attempt(
    database, booking_client
):
    client, _ = booking_client
    key = str(uuid4())

    def fail_clock(connection):
        raise RuntimeError("unexpected clock failure")

    original_clock = app.dependency_overrides[calendar_clock]
    app.dependency_overrides[calendar_clock] = lambda: fail_clock
    try:
        result = post(client, key=key)
        assert result.status_code == 500
        assert result.json() == {
            "code": "INTERNAL_ERROR",
            "message": "Внутренняя ошибка сервера",
        }
        assert result.headers["cache-control"] == "no-store"
        assert counts(database) == (0, 0)
    finally:
        app.dependency_overrides[calendar_clock] = original_clock
    assert post(client, key=key).status_code == 201
    assert counts(database) == (1, 1)
