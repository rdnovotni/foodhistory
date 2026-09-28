"""Small database boundary for the PostgreSQL-first application."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            connection.execute("SET search_path TO food_history, public")
            yield connection

    def fetch_one(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> dict[str, Any] | None:
        with self.connection() as connection:
            return connection.execute(query, parameters or ()).fetchone()

    def fetch_all(
        self, query: str, parameters: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return connection.execute(query, parameters or ()).fetchall()

    def ping(self) -> bool:
        return self.fetch_one("SELECT 1 AS ok") == {"ok": 1}
