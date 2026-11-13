"""Конфигурация запуска проверяется до обращения к PostgreSQL."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.start import server_port


@pytest.mark.parametrize("value", ["1", "8000", "9000", "65535"])
def test_configured_port(monkeypatch, value):
    monkeypatch.setenv("PORT", value)
    assert server_port() == value


def test_default_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert server_port() == "8000"


@pytest.mark.parametrize("module", ["app.start", "app.container_start"])
@pytest.mark.parametrize("value", ["", "0", "65536", "-1", "9000.0", "abc"])
def test_invalid_port_fails_before_database_start(module, value):
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=Path(__file__).resolve().parents[1],
        env={
            **os.environ,
            "PORT": value,
            "DATABASE_URL": "postgresql://127.0.0.1:1/unavailable",
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "PORT должен быть целым числом от 1 до 65535" in result.stderr
    assert "connection" not in result.stderr
    assert "Traceback" not in result.stderr
