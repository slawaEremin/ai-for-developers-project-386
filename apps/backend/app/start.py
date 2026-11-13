"""Подготовка должна завершиться успешно до запуска одного процесса Uvicorn."""

import os
import subprocess
import sys


def server_port():
    value = os.environ.get("PORT", "8000")
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 65535:
        raise ValueError("PORT должен быть целым числом от 1 до 65535")
    return str(int(value))


def main():
    try:
        port = server_port()
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    subprocess.run([sys.executable, "-m", "app.prepare"], check=True)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--workers",
            "1",
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
