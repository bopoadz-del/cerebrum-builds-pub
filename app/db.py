"""The one place that decides which database this platform runs on.

``DATABASE_URL`` present means PostgreSQL; absent means the SQLite file under
``STORAGE_PATH``.  ``app.store`` takes every connection from here, so a
setting the operator supplies cannot be read and ignored while the platform
quietly writes somewhere else.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

BUSY_TIMEOUT_MS = 30000
POOL_SIZE = 5
MAX_OVERFLOW = 10
DB_FILENAME = "platform.db"

_engines: Dict[str, Any] = {}


def database_url() -> Optional[str]:
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    return raw or None


def backend_name() -> str:
    return "postgres" if database_url() else "sqlite"


def storage_root() -> Path:
    raw = (os.environ.get("STORAGE_PATH") or "").strip()
    if not raw:
        raise RuntimeError("STORAGE_PATH is unset: the platform has no persistence root")
    return Path(raw)


def sqlite_path() -> Path:
    return storage_root() / DB_FILENAME


def _sqlalchemy_url() -> str:
    url = database_url()
    if url:
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    return "sqlite:///" + str(sqlite_path())


def engine():
    """The process engine for the CURRENT persistence setting.

    Engines are cached per URL: a test or a restore drill that points
    STORAGE_PATH at another root must not keep writing to the previous file
    through a stale pool.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import QueuePool

    url = _sqlalchemy_url()
    cached = _engines.get(url)
    if cached is not None:
        return cached
    kwargs: Dict[str, Any] = {
        "poolclass": QueuePool,
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_pre_ping": True,
        "future": True,
    }
    if url.startswith("sqlite"):
        root = storage_root()
        root.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {
            "timeout": BUSY_TIMEOUT_MS / 1000,
            "check_same_thread": False,
        }
    created = create_engine(url, **kwargs)

    if url.startswith("sqlite"):
        @event.listens_for(created, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _engines[url] = created
    return created


def connect():
    """A DB-API style connection.

    SQLite callers get the sqlite3 connection the suite can PRAGMA; Postgres
    callers get a SQLAlchemy Connection (``sqlalchemy.text`` for literals).
    """
    if backend_name() == "sqlite":
        root = storage_root()
        root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(sqlite_path()),
            timeout=BUSY_TIMEOUT_MS / 1000,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        return conn
    return engine().connect()


def reset_engine() -> None:
    """Test hook: drop every cached engine after the environment changes."""
    for created in list(_engines.values()):
        try:
            created.dispose()
        except Exception:
            pass
    _engines.clear()
