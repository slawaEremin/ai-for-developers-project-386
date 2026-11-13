"""Проверка собранного образа; удаляет только созданные этим прогоном ресурсы."""

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent


def docker(*args, check=True):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=120, cwd=ROOT
    )
    if check and result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    if args[0] == "logs":
        return result.stdout + result.stderr
    return result.stdout.strip()


def request(base, path, payload=None, key=None):
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    data = None if payload is None else json.dumps(payload).encode()
    with urlopen(
        Request(base + path, data=data, headers=headers), timeout=5
    ) as response:
        return response.status, response.read()


def ready(name, port):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if docker("inspect", "--format", "{{.State.Running}}", name) != "true":
            raise RuntimeError(docker("logs", name))
        address = docker("port", name, f"{port}/tcp").splitlines()[0]
        base = "http://" + address
        try:
            status, body = request(base, "/health")
            assert status == 200 and json.loads(body) == {"status": "ok"}
            return base
        except (URLError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"HTTP не готов: {name}\n{docker('logs', name)}")


def create_booking(base):
    status, page = request(base, "/")
    assert status == 200
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.decode())
    assert any(asset.endswith(".js") for asset in assets)
    assert any(asset.endswith(".css") for asset in assets)
    for asset in assets:
        status, body = request(base, asset)
        assert status == 200 and body and not body.startswith(b"<!doctype")
    status, _ = request(
        base,
        "/api/meeting-types",
        {
            "id": "consultation",
            "name": "Консультация",
            "description": "Проверка образа",
            "durationMinutes": 30,
        },
    )
    assert status == 201
    _, availability = request(base, "/api/meeting-types/consultation/availability")
    start = json.loads(availability)["days"][0]["slots"][0]["startsAt"]
    status, booking = request(
        base,
        "/api/bookings",
        {"meetingTypeId": "consultation", "startsAt": start},
        str(uuid4()),
    )
    assert status == 201
    return json.loads(booking)


def preserved(base, booking):
    _, catalog = request(base, "/api/meeting-types")
    assert len(json.loads(catalog)["items"]) == 1
    _, upcoming = request(base, "/api/bookings/upcoming")
    assert json.loads(upcoming)["items"] == [booking]


def stopped(name):
    docker("stop", "--time", "10", name)
    assert docker("inspect", "--format", "{{.State.ExitCode}}", name) == "0"
    logs = subprocess.run(
        ["docker", "logs", name], capture_output=True, text=True, check=True
    ).stderr
    assert logs.rindex("Application shutdown complete") < logs.rindex(
        "received fast shutdown request"
    )
    assert "database system is shut down" in logs


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "calendar"
    prefix = "calendar-check-" + uuid4().hex[:12]
    volume = prefix + "-data"
    names = []

    def launch(suffix, *options):
        name = prefix + "-" + suffix
        names.append(name)
        docker("run", "-d", "--name", name, *options, image)
        return name

    docker("volume", "create", volume)
    with tempfile.TemporaryDirectory(prefix="calendar-compose-") as temporary:
        override = Path(temporary) / "override.yaml"
        override.write_text(
            "services:\n"
            f"  app:\n    image: {json.dumps(image)}\n"
            "    environment:\n      PORT: '9001'\n"
            "    ports: !override ['127.0.0.1::9001']\n"
        )
        compose = (
            "compose",
            "-p",
            prefix,
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
        )
        try:
            name = launch(
                "standalone",
                "-e",
                "PORT=9000",
                "-e",
                "DATABASE_URL=postgresql://app@127.0.0.1:1/ignored",
                "-p",
                "127.0.0.1::9000",
                "-v",
                volume + ":/app/data",
            )
            base = ready(name, 9000)
            assert docker("exec", name, "id", "-u") == "10001"
            assert docker("exec", name, "postgres", "--version").startswith(
                "postgres (PostgreSQL) 17."
            )
            docker(
                "exec",
                name,
                "python",
                "-c",
                "import glob, psycopg; "
                "c = psycopg.connect(dbname='calendar', user='app', "
                "host=glob.glob('/tmp/calendar-pg-*')[0]); "
                "assert c.execute('SHOW listen_addresses').fetchone() == ('',)",
            )
            booking = create_booking(base)
            stopped(name)
            docker("start", name)
            preserved(ready(name, 9000), booking)
            stopped(name)
            docker("rm", name)
            print("PORT=9000, статика, бронирование и перезапуск: OK", flush=True)

            name = launch(
                "default", "-p", "127.0.0.1::8000", "-v", volume + ":/app/data"
            )
            preserved(ready(name, 8000), booking)
            docker(
                "exec",
                name,
                "python",
                "-c",
                "import os, signal, pathlib; "
                "pid=int(pathlib.Path('/app/data/pgdata/postmaster.pid')"
                ".read_text().splitlines()[0]); os.kill(pid, signal.SIGKILL)",
            )
            assert docker("wait", name) == "1"
            print("PORT по умолчанию, сохранность тома и отказ БД: OK", flush=True)

            name = launch(
                "http-failure", "-p", "127.0.0.1::8000", "-v", volume + ":/app/data"
            )
            preserved(ready(name, 8000), booking)
            docker(
                "exec",
                name,
                "python",
                "-c",
                "import os, signal, pathlib; "
                "pids=[int(p.parent.name) for p in pathlib.Path('/proc').glob('[0-9]*/cmdline') "
                "if p.read_bytes().split(b'\\0')[1:3] == [b'-m', b'uvicorn']]; "
                "assert len(pids)==1; os.kill(pids[0], signal.SIGKILL)",
            )
            assert docker("wait", name) == "1"
            print("Восстановление после сбоя и отказ HTTP: OK", flush=True)

            for index, setting in enumerate(
                [
                    "PORT=0",
                    "PORT=65536",
                    "PORT=abc",
                ]
            ):
                name = launch(f"invalid-{index}", "-e", setting)
                assert docker("wait", name) == "1"
                assert (
                    docker("inspect", "--format", "{{.State.Running}}", name) == "false"
                )
            assert (
                docker(
                    "run",
                    "--rm",
                    image,
                    "python",
                    "-c",
                    "from pathlib import Path; "
                    "assert not Path('/app/data/pgdata').exists(); "
                    "assert not Path('/var/lib/postgresql/17/main').exists(); "
                    "print('override')",
                )
                == "override"
            )
            print("Ошибки конфигурации и переопределение команды: OK", flush=True)

            docker(*compose, "up", "-d", "--no-build", "app")
            application = docker(*compose, "ps", "-q", "app")
            booking = create_booking(ready(application, 9001))
            assert docker(*compose, "ps", "--services", "--status", "running") == "app"
            docker(*compose, "down")
            docker(*compose, "up", "-d", "--no-build", "app")
            application = docker(*compose, "ps", "-q", "app")
            preserved(ready(application, 9001), booking)
            stopped(application)
            print("Автономный Compose и сохранность его тома: OK", flush=True)
        finally:
            docker(*compose, "down", "--volumes", check=False)
            for name in names:
                docker("rm", "-f", name, check=False)
            docker("volume", "rm", volume, check=False)


if __name__ == "__main__":
    main()
