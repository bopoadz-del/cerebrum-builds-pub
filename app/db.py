"""One place decides which database the platform runs on.

``DATABASE_URL`` present means Postgres; absent means the SQLite file under
``STORAGE_PATH``. ``app/store.py`` takes every connection from here, so the
two can never disagree about where the data lives.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

PLATFORM_DB = "platform.db"
SQLITE_BUSY_TIMEOUT_MS = 30000


def database_url() -> str:
    return (os.getenv("DATABASE_URL") or "").strip()


def backend_name() -> str:
    return "postgres" if database_url() else "sqlite"


def sqlite_path() -> Path:
    root = (os.getenv("STORAGE_PATH") or ".").strip() or "."
    return Path(root) / PLATFORM_DB


_SHARED_LOCK = threading.RLock()
_SHARED: dict = {"key": None, "conn": None}


def shared() -> Any:
    """One process-wide connection per database, guarded by the caller's lock.

    Opening a fresh write transaction per request is expensive on a shared
    disk; the store serialises access, so one connection is both safe and
    honest about the single persistence root."""
    key = database_url() or str(sqlite_path())
    with _SHARED_LOCK:
        if _SHARED["key"] == key and _SHARED["conn"] is not None:
            return _SHARED["conn"]
        close_shared()
        if backend_name() == "postgres":
            conn = _PgConnection()
        else:
            path = sqlite_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0,
                                   check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = %d" % SQLITE_BUSY_TIMEOUT_MS)
            conn.execute("PRAGMA synchronous = NORMAL")
        _SHARED["key"] = key
        _SHARED["conn"] = conn
        return conn


def close_shared() -> None:
    with _SHARED_LOCK:
        conn = _SHARED.get("conn")
        _SHARED["key"] = None
        _SHARED["conn"] = None
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _sqlite_connect() -> sqlite3.Connection:
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(path),
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = %d" % SQLITE_BUSY_TIMEOUT_MS)
    return conn


class _PgConnection:
    """A DB-API-shaped view over a SQLAlchemy Postgres connection."""

    def __init__(self) -> None:
        from sqlalchemy import create_engine

        url = database_url()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        self._engine = create_engine(url, pool_pre_ping=True)
        self._conn = self._engine.connect()

    def execute(self, sql: str, params: Any = ()) -> Any:
        return self._conn.exec_driver_sql(sql, params or ())

    def executemany(self, sql: str, seq: Any) -> Any:
        return self._conn.exec_driver_sql(sql, list(seq))

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
        self._engine.dispose()


def connect() -> Any:
    if backend_name() == "postgres":
        return _PgConnection()
    return _sqlite_connect()
