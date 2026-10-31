"""One place that decides the database backend.

``DATABASE_URL`` present means Postgres; absent means SQLite under
``STORAGE_PATH``. Every persistence path (store, migrations, health,
backups) asks this module for a connection or the engine, so the backend
the operator configured is the backend the platform actually uses.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

DEFAULT_DB_NAME = "platform.db"
SQLITE_BUSY_TIMEOUT_MS = 30_000
POOL_SIZE = 5
MAX_OVERFLOW = 10

_engine: Optional[Engine] = None
_engine_key: Optional[str] = None


def storage_root() -> Path:
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    return Path(raw) if raw else Path("data")


def sqlite_path() -> Path:
    return storage_root() / DEFAULT_DB_NAME


def database_url() -> str:
    configured = (os.getenv("DATABASE_URL") or "").strip()
    if configured:
        return configured
    sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(sqlite_path().resolve())


def backend_name() -> str:
    return "postgres" if (os.getenv("DATABASE_URL") or "").strip() else "sqlite"


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0}
    return {}


def engine() -> Engine:
    """The process engine, rebuilt when STORAGE_PATH/DATABASE_URL changes.

    The suite and the request path both monkeypatch STORAGE_PATH; caching by
    URL keeps those isolated runs from writing into the previous database.
    """
    global _engine, _engine_key
    url = database_url()
    if _engine is not None and _engine_key == url:
        return _engine
    if _engine is not None:
        _engine.dispose()
    kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "future": True,
        "connect_args": _connect_args(url),
    }
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = POOL_SIZE
        kwargs["max_overflow"] = MAX_OVERFLOW
    _engine = create_engine(url, **kwargs)
    _engine_key = url
    return _engine


def connect():
    """A DB-API connection for the live backend.

    SQLite callers receive a sqlite3 connection (PRAGMA works); a configured
    Postgres deployment receives a SQLAlchemy connection.
    """
    if backend_name() == "sqlite":
        path = sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn
    return engine().connect()


def enable_wal() -> str:
    if backend_name() != "sqlite":
        return "postgres"
    conn = connect()
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        return str(mode)
    finally:
        conn.close()
