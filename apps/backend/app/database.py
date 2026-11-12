import os

import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(
        os.environ.get(
            "DATABASE_URL", "postgresql://calendar:calendar@127.0.0.1:55431/calendar"
        ),
        connect_timeout=3,
        row_factory=dict_row,
    )
