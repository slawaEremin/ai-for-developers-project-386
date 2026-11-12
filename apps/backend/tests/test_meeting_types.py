"""Публичный HTTP-сценарий с настоящим PostgreSQL (TEST_DATABASE_URL)."""

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from app.main import app
from app.prepare import prepare_database

PAYLOAD = {
    "id": "consultation",
    "name": "Консультация",
    "description": "Разберём вопросы",
    "durationMinutes": 30,
}


pytestmark = pytest.mark.usefixtures("database")


def test_owner_creates_type_and_it_survives_preparation_and_application_restart():
    with TestClient(app) as client:
        result = client.post("/api/meeting-types", json=PAYLOAD)
        assert result.status_code == 201
        assert result.json() == PAYLOAD
        assert result.headers["cache-control"] == "no-store"
    prepare_database()
    with TestClient(app) as restarted:
        duplicate = restarted.post(
            "/api/meeting-types", json={**PAYLOAD, "name": "Другое"}
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "MEETING_TYPE_ID_CONFLICT"


@pytest.mark.parametrize("duration", [1, 30, 30.0, 45, 540])
def test_numeric_integer_durations_are_accepted(duration):
    with TestClient(app) as client:
        response = client.post(
            "/api/meeting-types", json={**PAYLOAD, "durationMinutes": duration}
        )
        assert response.status_code == 201
        assert response.json()["durationMinutes"] == duration


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", "A"),
        ("id", "-a"),
        ("id", "a-"),
        ("id", " a"),
        ("id", "a "),
        ("id", "а"),
        ("id", "a" * 65),
        ("name", " \n\t"),
        ("name", "a\nb"),
        ("name", "a\rb"),
        ("name", "я" * 121),
        ("description", " \n"),
        ("description", "я" * 2001),
        ("durationMinutes", -1),
        ("durationMinutes", 0),
        ("durationMinutes", 541),
        ("durationMinutes", 30.5),
        ("durationMinutes", "30"),
        ("durationMinutes", True),
        ("durationMinutes", None),
        ("name", 30),
        ("description", False),
    ],
)
def test_invalid_fields_are_rejected_without_creating_type(field, value):
    with TestClient(app) as client:
        response = client.post("/api/meeting-types", json={**PAYLOAD, field: value})
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert field in response.json()["fieldErrors"]
        assert response.headers["cache-control"] == "no-store"
        assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 201


@pytest.mark.parametrize("field", list(PAYLOAD))
@pytest.mark.parametrize("kind", ["missing", "null"])
def test_all_fields_are_required_and_non_nullable(field, kind):
    body = dict(PAYLOAD)
    if kind == "missing":
        del body[field]
    else:
        body[field] = None
    with TestClient(app) as client:
        response = client.post("/api/meeting-types", json=body)
        assert response.status_code == 422
        assert field in response.json()["fieldErrors"]


def test_text_is_trimmed_unicode_counted_and_plain_text_preserved():
    body = {
        "id": "a" + "-" * 62 + "9",
        "name": "\t" + "😀" * 120 + " \n",
        "description": " \n" + "<b>текст</b>  **обычный**\n" + "я" * 1974 + "\n ",
        "durationMinutes": 45,
    }
    with TestClient(app) as client:
        response = client.post("/api/meeting-types", json=body)
        assert response.status_code == 201
        assert response.json() == {
            **body,
            "name": "😀" * 120,
            "description": "<b>текст</b>  **обычный**\n" + "я" * 1974,
        }
        single = client.post("/api/meeting-types", json={**PAYLOAD, "id": "a"})
        assert single.status_code == 201


@pytest.mark.parametrize(
    ("body", "content_type", "status", "code"),
    [
        ("{", "application/json", 400, "BAD_REQUEST"),
        ("{}", "text/plain", 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("{}", None, 415, "UNSUPPORTED_MEDIA_TYPE"),
        ("[]", "application/json", 422, "VALIDATION_ERROR"),
        ("null", "application/json", 422, "VALIDATION_ERROR"),
    ],
)
def test_json_errors_have_contract_shape_and_no_store(body, content_type, status, code):
    headers = {"Content-Type": content_type} if content_type else {}
    with TestClient(app) as client:
        response = client.post("/api/meeting-types", content=body, headers=headers)
        assert response.status_code == status
        assert response.json()["code"] == code
        assert isinstance(response.json()["message"], str)
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/json"


def test_unknown_fields_are_rejected():
    with TestClient(app) as client:
        result = client.post("/api/meeting-types", json={**PAYLOAD, "extra": 1})
        assert result.status_code == 422
        assert result.json()["fieldErrors"]["extra"]


def test_database_outage_returns_503_and_prevents_preparation(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:1/calendar"
    )
    with pytest.raises(psycopg.OperationalError):
        prepare_database()
    with TestClient(app) as client:
        response = client.post("/api/meeting-types", json=PAYLOAD)
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
        assert response.headers["cache-control"] == "no-store"


def test_initial_preparation_is_empty_and_repeated_preparation_preserves_owner(
    database, monkeypatch
):
    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT id FROM meeting_types").fetchall() == []
        assert connection.execute("SELECT id, name FROM owners").fetchall() == [
            (1, "Владелец календаря")
        ]
    monkeypatch.setenv("OWNER_NAME", "Другой владелец")
    prepare_database()
    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT id, name FROM owners").fetchall() == [
            (1, "Владелец календаря")
        ]
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [("001_owner_and_meeting_types.sql",), ("002_bookings.sql",)]


def test_duplicate_never_changes_stored_type(database):
    with TestClient(app) as client:
        assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 201
        assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 409
        assert (
            client.post(
                "/api/meeting-types", json={**PAYLOAD, "name": "Перезаписать"}
            ).status_code
            == 409
        )
    with psycopg.connect(database) as connection:
        assert connection.execute(
            "SELECT id, name, description, duration_minutes FROM meeting_types"
        ).fetchall() == [("consultation", "Консультация", "Разберём вопросы", 30)]


@pytest.mark.parametrize(
    ("name", "description"),
    [("я", "😀"), ("a  b", "Строка  один\nСтрока два")],
)
def test_minimum_text_and_internal_whitespace_are_preserved(name, description):
    body = {**PAYLOAD, "name": name, "description": description}
    with TestClient(app) as client:
        assert client.post("/api/meeting-types", json=body).json() == body
        assert (
            client.post(
                "/api/meeting-types", json={**body, "id": "same--name"}
            ).status_code
            == 201
        )


def test_invalid_utf8_is_a_bad_json_request():
    with TestClient(app) as client:
        result = client.post(
            "/api/meeting-types",
            content=b"\xff",
            headers={"Content-Type": "application/json"},
        )
        assert result.status_code == 400
        assert result.json()["code"] == "BAD_REQUEST"
        assert result.headers["cache-control"] == "no-store"


def test_catalog_is_empty_then_created_type_is_available_after_restart():
    with TestClient(app) as client:
        empty = client.get("/api/meeting-types")
        assert empty.status_code == 200
        assert empty.json()["items"] == []
        assert empty.json()["serverTime"].endswith("Z")
        assert empty.headers["cache-control"] == "no-store"
        assert client.post("/api/meeting-types", json=PAYLOAD).status_code == 201
    prepare_database()
    with TestClient(app) as restarted:
        catalog = restarted.get("/api/meeting-types")
        assert catalog.json()["items"] == [PAYLOAD]
        single = restarted.get("/api/meeting-types/consultation")
        assert single.status_code == 200
        assert single.json() == PAYLOAD
        assert single.headers["cache-control"] == "no-store"
        assert single.headers["content-type"] == "application/json"


def test_catalog_orders_names_then_ids_by_unicode_code_point():
    with TestClient(app) as client:
        for id, name in [
            ("z", "a"),
            ("emoji", "😀"),
            ("b", "a"),
            ("cyrillic", "Я"),
            ("capital", "A"),
            ("bmp", "\ue000"),
        ]:
            assert (
                client.post(
                    "/api/meeting-types", json={**PAYLOAD, "id": id, "name": name}
                ).status_code
                == 201
            )
        response = client.get("/api/meeting-types")
        assert [item["id"] for item in response.json()["items"]] == [
            "capital",
            "b",
            "z",
            "cyrillic",
            "bmp",
            "emoji",
        ]


@pytest.mark.parametrize(
    ("id", "status", "code"),
    [
        ("Missing", 422, "VALIDATION_ERROR"),
        ("a-", 422, "VALIDATION_ERROR"),
        ("a" * 65, 422, "VALIDATION_ERROR"),
        ("missing--type", 404, "MEETING_TYPE_NOT_FOUND"),
    ],
)
def test_get_type_distinguishes_invalid_id_and_missing_type(id, status, code):
    with TestClient(app) as client:
        response = client.get("/api/meeting-types/" + id)
        assert response.status_code == status
        assert response.json()["code"] == code
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "path", ["/api/meeting-types", "/api/meeting-types/consultation"]
)
def test_reading_types_reports_database_outage(path, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:1/calendar"
    )
    with TestClient(app) as client:
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
        assert response.headers["cache-control"] == "no-store"


def test_catalog_server_time_is_utc_regardless_of_database_session_zone(
    database, monkeypatch
):
    monkeypatch.setenv(
        "DATABASE_URL",
        make_conninfo(
            database,
            options=psycopg.conninfo.conninfo_to_dict(database)["options"]
            + " -c timezone=Europe/Moscow",
        ),
    )
    with TestClient(app) as client:
        response = client.get("/api/meeting-types")
        assert response.status_code == 200
        assert response.json()["serverTime"].endswith("Z")
