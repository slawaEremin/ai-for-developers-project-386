"""Настоящее приложение для Playwright в отдельной схеме PostgreSQL."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "apps/backend"
sys.path.insert(0, str(BACKEND))
from app.prepare import prepare_database


def main():
    database_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:55431/calendar"
    )
    schema = "calendar_e2e_" + uuid4().hex
    with psycopg.connect(database_url) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    server = None
    try:
        os.environ["DATABASE_URL"] = make_conninfo(
            database_url, options=f"-c search_path={schema}"
        )
        os.environ["STATIC_DIR"] = str(ROOT / "apps/frontend/dist")
        prepare_database()
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=BACKEND,
        )
        deadline = time.monotonic() + 20
        while True:
            if server.poll() is not None:
                raise RuntimeError("HTTP-сервер завершился до запуска браузера")
            try:
                with urlopen(base_url + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "HTTP-сервер не запустился за 20 секунд"
                    ) from None
                time.sleep(0.1)
        result = subprocess.run(
            [
                "npx",
                "--no-install",
                "playwright",
                "test",
                "--config",
                "apps/frontend/playwright.config.ts",
            ],
            cwd=ROOT,
            env={**os.environ, "E2E_BASE_URL": base_url},
            check=False,
        )
        return result.returncode
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        # Имя генерируется этим прогоном; public и чужие тестовые схемы не трогаем.
        with psycopg.connect(database_url) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


if __name__ == "__main__":
    raise SystemExit(main())
