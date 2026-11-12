"""Отдельная обязательная команда подготовки: python -m app.prepare."""

import logging
import os
from pathlib import Path

from app.database import connect


def prepare_database():
    with connect() as connection:
        # Повторный или одновременный запуск подготовки не повторяет миграции.
        connection.execute("SELECT pg_advisory_xact_lock(386)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        for migration in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
            if not connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (migration.name,)
            ).fetchone():
                connection.execute(migration.read_text())
                connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration.name,),
                )
        connection.execute(
            "INSERT INTO owners (id, name) VALUES (1, %s) ON CONFLICT (id) DO NOTHING",
            (os.environ.get("OWNER_NAME", "Владелец календаря"),),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    prepare_database()
    logging.info("База данных подготовлена; владелец и существующие данные сохранены")
