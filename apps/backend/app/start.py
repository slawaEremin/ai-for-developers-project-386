"""Подготовка должна завершиться успешно до запуска одного процесса Uvicorn."""

import os
import subprocess
import sys

if __name__ == "__main__":
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
            "8000",
            "--workers",
            "1",
        ],
    )
