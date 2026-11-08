"""One place decides the database backend.

``DATABASE_URL`` present means Postgres; absent means SQLite under
``STORAGE_PATH``. Nothing else in the platform opens a database of its own.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

SQLITE_BUSY_TIMEOUT_MS = 15_000
_engine: Optional[Engine] = None
_engine_url: Optional[str] = None

DB_FILENAME = "platform.db"


def backend_name() -> str:
    return "postgres" if (os.getenv("DATABASE_URL") or "").strip() else "sqlite"


def _normalise_postgres(url: str) -> str:
    """Drive Postgres through psycopg 3 (the driver this image installs)."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return _normalise_postgres(raw)
    return "sqlite:///" + str(sqlite_path())


def sqlite_path() -> Path:
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    if not raw:
        raise RuntimeError("STORAGE_PATH is not set: no persistence root declared")
    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    return root / DB_FILENAME


def _sqlite_timeout_s() -> float:
    raw = (os.getenv("SQLITE_BUSY_TIMEOUT_MS") or "").strip()
    try:
        return max(1, int(raw)) / 1000.0
    except ValueError:
        return SQLITE_BUSY_TIMEOUT_MS / 1000.0


def connect():
    """A connection on the live backend. Never a second database."""
    if backend_name() == "sqlite":
        path = sqlite_path()
        conn = sqlite3.connect(
            str(path),
            timeout=_sqlite_timeout_s(),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        return conn
    return get_engine().connect()


def get_engine() -> Engine:
    global _engine, _engine_url
    url = database_url()
    if _engine is None or _engine_url != url:
        if backend_name() == "sqlite":
            sqlite_path().parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(
                url,
                future=True,
                pool_size=5,
                max_overflow=10,
                connect_args={
                    "timeout": _sqlite_timeout_s(),
                    "check_same_thread": False,
                },
            )
        else:
            _engine = create_engine(
                url, future=True, pool_pre_ping=True, pool_size=5, max_overflow=10
            )
        _engine_url = url
    return _engine


def engine():
    """The engine the store and the concurrency probe read."""
    return get_engine()


def reset_engine() -> None:
    global _engine, _engine_url
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:  # noqa: BLE001 -- a dead engine is replaced, not fatal
            pass
    _engine = None
    _engine_url = None
