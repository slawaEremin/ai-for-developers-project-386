"""Изолированная реальная PostgreSQL без очистки схемы приложения."""

import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.prepare import prepare_database


@pytest.fixture
def database(monkeypatch):
    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:55431/calendar"
    )
    schema = "calendar_test_" + uuid4().hex
    with psycopg.connect(url) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    isolated_url = make_conninfo(url, options=f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URL", isolated_url)
    monkeypatch.setenv("OWNER_NAME", "Владелец календаря")
    try:
        prepare_database()
        yield isolated_url
    finally:
        with psycopg.connect(url) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
