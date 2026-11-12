"""Единый источник времени сценария; тесты заменяют зависимость calendar_clock."""


def database_time(connection):
    return connection.execute("SELECT clock_timestamp() AS time").fetchone()["time"]


def calendar_clock():
    return database_time
