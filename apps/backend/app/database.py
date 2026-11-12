import os
from time import monotonic

import psycopg
from psycopg.rows import dict_row


class DeadlineConnection(psycopg.Connection):
    """Один абсолютный бюджет для SQL, ожидания сокета и COMMIT."""

    deadline = float("inf")

    def remaining(self):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            self.close()
            raise psycopg.OperationalError("Booking transaction deadline expired")
        return remaining

    def wait(self, gen, interval=0.1, timeout=None):
        remaining = self.remaining()
        try:
            return super().wait(
                gen,
                interval=interval,
                timeout=remaining if timeout is None else min(timeout, remaining),
            )
        except psycopg.OperationalError:
            # Закрываем сокет без дополнительного ожидания rollback/cancel.
            # Если это был COMMIT, его исход остаётся неизвестным.
            self.close()
            raise

    def limit_statement(self):
        milliseconds = max(1, int(self.remaining() * 1000))
        super().execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (str(milliseconds),),
        )

    def execute(self, query, params=None, **kwargs):
        self.limit_statement()
        return super().execute(query, params, **kwargs)

    def commit(self):
        self.limit_statement()
        return super().commit()


def connect(*, deadline=None):
    timeout = 3
    connection_class = psycopg.Connection
    if deadline is not None:
        remaining = deadline - monotonic()
        # libpq округляет малые connect_timeout до двух секунд. Не начинаем
        # соединение, которое уже не помещается в оставшийся бюджет.
        if remaining < 2:
            raise psycopg.OperationalError("Insufficient booking connection budget")
        timeout = min(timeout, int(remaining))
        connection_class = DeadlineConnection
    connection = connection_class.connect(
        os.environ.get(
            "DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:55431/calendar"
        ),
        connect_timeout=timeout,
        row_factory=dict_row,
    )
    if deadline is not None:
        connection.deadline = deadline
        connection.remaining()
    return connection
