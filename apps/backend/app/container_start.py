"""Автономная БД и HTTP-сервер с общим жизненным циклом контейнера."""

import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

from app.start import server_port

DATA = Path("/app/data/pgdata")


class ShutdownRequested(BaseException):
    pass


def request_shutdown(signum, frame):
    raise ShutdownRequested


def stop_process(process, *, database=False):
    if process is None:
        return
    try:
        if database:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)  # PostgreSQL: fast shutdown.
        else:
            # Подготовка и Uvicorn принадлежат одной отдельной группе процессов.
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=3 if database else 5)
    except ProcessLookupError:
        process.wait()
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def initialize_database():
    if (DATA / "PG_VERSION").exists():
        return
    process = subprocess.Popen(
        [
            "initdb",
            "-D",
            str(DATA),
            "--username=app",
            "--encoding=UTF8",
            "--locale=C.UTF-8",
            "--auth-local=peer",
            "--auth-host=reject",
        ],
        start_new_session=True,
    )
    try:
        if process.wait() != 0:
            raise RuntimeError("Не удалось инициализировать PostgreSQL")
    finally:
        stop_process(process)


def prepare_local_database(process, socket):
    bootstrap = make_conninfo(dbname="postgres", user="app", host=socket)
    deadline = time.monotonic() + 30
    while True:
        if process.poll() is not None:
            raise RuntimeError("PostgreSQL завершился до готовности")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("PostgreSQL не готов за 30 секунд")
        try:
            with psycopg.connect(
                bootstrap,
                connect_timeout=1,
                options=f"-c statement_timeout={max(1, int(remaining * 1000))}",
                autocommit=True,
            ) as connection:
                connection.execute("SELECT 1")
                break
        except psycopg.OperationalError:
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    with psycopg.connect(bootstrap, autocommit=True, connect_timeout=3) as connection:
        if not connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'calendar'"
        ).fetchone():
            connection.execute("CREATE DATABASE calendar")
    return make_conninfo(dbname="calendar", user="app", host=socket)


def run(socket):
    database = None
    application = None
    try:
        environment = os.environ.copy()
        initialize_database()
        database = subprocess.Popen(
            [
                "postgres",
                "-D",
                str(DATA),
                "-k",
                socket,
                "-c",
                "listen_addresses=",
                "-c",
                "unix_socket_permissions=0700",
            ],
            start_new_session=True,
        )
        environment["DATABASE_URL"] = prepare_local_database(database, socket)
        application = subprocess.Popen(
            [sys.executable, "-m", "app.start"],
            env=environment,
            start_new_session=True,
        )
        while True:
            if database.poll() is not None:
                raise RuntimeError("Встроенный PostgreSQL неожиданно завершился")
            if application.poll() is not None:
                raise RuntimeError(
                    f"HTTP-процесс завершился с кодом {application.returncode}"
                )
            time.sleep(0.1)
    except ShutdownRequested:
        return 0
    finally:
        # Повторный сигнал не должен прервать последовательное завершение.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            stop_process(application)
        finally:
            stop_process(database, database=True)


def main():
    logging.basicConfig(level=logging.INFO)
    try:
        server_port()  # Ошибка конфигурации обнаруживается до создания БД.
        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)
        with tempfile.TemporaryDirectory(prefix="calendar-pg-") as socket:
            return run(socket)
    except ShutdownRequested:
        return 0
    except (ValueError, RuntimeError, OSError, psycopg.Error) as error:
        logging.error("Ошибка запуска контейнера: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
