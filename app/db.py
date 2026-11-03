"""One place decides which database the platform runs on.

DATABASE_URL present means Postgres; absent means SQLite under the
STORAGE_PATH root. app.db is the only module that opens a database: the
store, the health probe and the migrations all take their connection from
here, so the two can never disagree about where the rows live.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

_TRUTHY_BUSY_MS = 5000


def backend_name() -> str:
    return "postgres" if DATABASE_URL.lower().startswith(("postgres://", "postgresql://")) else "sqlite"


def storage_root() -> Path:
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    if not raw:
        raise RuntimeError("STORAGE_PATH is not set: the platform has no persistence root")
    return Path(raw)


def sqlite_path() -> Path:
    if DATABASE_URL.lower().startswith("sqlite:///"):
        return Path(DATABASE_URL[len("sqlite:///"):])
    return storage_root() / "platform.db"


def database_url() -> str:
    if backend_name() == "postgres":
        return DATABASE_URL
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(path)


def connect():
    """A DB-API connection from the one configured backend.

    SQLite connections carry the busy timeout (concurrent writers wait
    rather than fail), foreign keys, and row access by column name. The
    journal mode is set once by the boot path (migrations), never here:
    switching WAL per connection races into 'database is locked'.
    """
    if backend_name() == "postgres":
        import psycopg

        return psycopg.connect(DATABASE_URL, autocommit=True)
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=_TRUTHY_BUSY_MS / 1000.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def enable_wal() -> None:
    """Set the declared journal mode on the SQLite file, once, at boot."""
    if backend_name() != "sqlite":
        return
    conn = sqlite3.connect(str(sqlite_path()))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def rows_as_dicts(cursor: Any) -> list[dict]:
    names = [d[0] for d in (cursor.description or [])]
    return [dict(zip(names, row)) for row in cursor.fetchall()]
