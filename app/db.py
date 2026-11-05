"""One place decides the database.

``DATABASE_URL`` present means Postgres; absent means SQLite under
``STORAGE_PATH``. ``app.store`` takes every connection from here, so a set
DATABASE_URL cannot be read and then ignored.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_NAME = "platform.db"
BUSY_TIMEOUT_MS = 30000
POOL_SIZE = 10
MAX_OVERFLOW = 20

_engine = None
_engine_lock = threading.Lock()


class _PostgresConnection:
    """DB-API-shaped facade over a SQLAlchemy connection."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, statement: Any, parameters: Any = None):
        from sqlalchemy import text

        if isinstance(statement, str):
            statement = text(statement)
        if parameters is None:
            result = self._connection.execute(statement)
        else:
            result = self._connection.execute(statement, parameters)
        return result

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def cursor(self):
        return self._connection.connection.cursor()


def database_url() -> Optional[str]:
    value = (os.environ.get("DATABASE_URL") or "").strip()
    return value or None


def backend_name() -> str:
    return "postgres" if database_url() else "sqlite"


def storage_root() -> Path:
    raw = (os.environ.get("STORAGE_PATH") or "").strip()
    return Path(raw) if raw else Path("data")


def sqlite_path() -> Path:
    return storage_root() / DEFAULT_DB_NAME


def sqlite_url() -> str:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(path)


def url() -> str:
    return database_url() or sqlite_url()


def engine():
    """The SQLAlchemy engine for the selected backend (created once)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from sqlalchemy import create_engine

                target = url()
                if target.startswith("sqlite"):
                    _engine = create_engine(
                        target,
                        connect_args={"check_same_thread": False, "timeout": BUSY_TIMEOUT_MS / 1000.0},
                        pool_size=POOL_SIZE,
                        max_overflow=MAX_OVERFLOW,
                        future=True,
                    )
                else:
                    _engine = create_engine(
                        target,
                        pool_size=POOL_SIZE,
                        max_overflow=MAX_OVERFLOW,
                        pool_pre_ping=True,
                        future=True,
                    )
    return _engine


def connect():
    """A connection on the selected backend. Never creates schema."""
    if backend_name() == "postgres":
        return _PostgresConnection(engine().connect())
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_MS / 1000.0, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def enable_wal() -> None:
    """Switch the SQLite file to WAL once, from the boot path."""
    if backend_name() != "sqlite":
        return
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_MS / 1000.0)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.commit()
    finally:
        connection.close()


def reset_engine() -> None:
    """Tests that move STORAGE_PATH between cases need a fresh engine."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
