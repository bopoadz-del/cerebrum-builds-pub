"""The one place that decides which database the platform runs on.

``DATABASE_URL`` present means Postgres; absent means a SQLite file under
``STORAGE_PATH``. Nothing else in the product opens a database, so the two
cannot disagree: a store that opened its own handle would let an operator set
DATABASE_URL, believe they are on Postgres, and still write SQLite onto the
container disk.

``connect()`` returns a DB-API style connection (sqlite3 on SQLite, a
SQLAlchemy connection on Postgres) for health probes and PRAGMA checks;
``engine()`` returns the SQLAlchemy engine the store issues Core statements
through.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app import config

#: The platform's one database file under STORAGE_PATH.
DB_FILENAME = "platform.db"

#: A concurrent write waits for the lock instead of failing outright. The boot
#: path switches the file to WAL; the timeout covers the write that still
#: queues behind a checkpoint.
SQLITE_BUSY_TIMEOUT_MS = 15000

#: The busy-timeout statement, as one constant: no SQL is built at run time.
SQLITE_BUSY_TIMEOUT_SQL = "PRAGMA busy_timeout = 15000"

#: WAL with synchronous=NORMAL: a commit is not an fsync storm, and the write
#: is still durable across an application crash (WAL replays). The journal mode
#: itself is a property of the file, set once by the boot path.
SQLITE_SYNCHRONOUS_SQL = "PRAGMA synchronous=NORMAL"

#: Pool shape: the concurrency check drives 2x (pool_size + max_overflow)
#: simultaneous creates, so the pool is bounded and generous but never
#: unbounded, and a write path never checks out a second connection while
#: holding one.
POOL_SIZE = 5
MAX_OVERFLOW = 10

_ENGINE_LOCK = threading.Lock()
_ENGINE: Optional[Engine] = None
_ENGINE_KEY: Optional[str] = None


def sqlite_path() -> Path:
    """The SQLite file app.db actually uses.

    ``DATABASE_URL`` decides: when it names a SQLite file, that file is the
    database (an operator-supplied URL is never silently ignored); otherwise
    the one file under STORAGE_PATH is. Reads, writes, migrations and the
    health probe all come through here, so they cannot disagree.
    """
    configured = (os.environ.get("DATABASE_URL") or "").strip()
    prefix = "sqlite:///"
    if configured.startswith(prefix):
        raw = configured[len(prefix):]
        if raw and raw != ":memory:":
            path = Path(raw)
            if not path.is_absolute():
                path = config.storage_root() / path
            return path
    return config.storage_root() / DB_FILENAME


def database_url() -> str:
    """The configured URL, or the SQLite file this process owns."""
    configured = (os.environ.get("DATABASE_URL") or "").strip()
    if configured:
        for bare in ("postgres://", "postgresql://"):
            if configured.startswith(bare):
                return "postgresql+psycopg://" + configured[len(bare):]
        return configured
    return "sqlite:///" + str(sqlite_path())


def backend_name() -> str:
    configured = (os.environ.get("DATABASE_URL") or "").strip()
    if not configured:
        return "sqlite"
    return "postgres" if configured.startswith(("postgres", "postgresql")) else "sqlite"


def engine() -> Engine:
    """The SQLAlchemy engine for the live backend (one per configuration)."""
    global _ENGINE, _ENGINE_KEY
    url = database_url()
    key = url + "|" + str(config.sync_threadpool())
    with _ENGINE_LOCK:
        if _ENGINE is not None and _ENGINE_KEY == key:
            return _ENGINE
        backend = backend_name()
        if backend == "sqlite":
            path = sqlite_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            eng = create_engine(
                "sqlite:///" + str(path),
                future=True,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=30,
                pool_pre_ping=True,
                connect_args={"timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0, "check_same_thread": False},
            )
        else:
            eng = create_engine(
                url,
                future=True,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=30,
                pool_pre_ping=True,
            )
        if backend == "sqlite":
            @event.listens_for(eng, "connect")
            def _sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute(SQLITE_BUSY_TIMEOUT_SQL)
                    cursor.execute(SQLITE_SYNCHRONOUS_SQL)
                finally:
                    cursor.close()

        _ENGINE = eng
        _ENGINE_KEY = key
        return eng


def reset_engine() -> None:
    """Drop the cached engine (a test or a rollback drill changed the URL)."""
    global _ENGINE, _ENGINE_KEY
    with _ENGINE_LOCK:
        if _ENGINE is not None:
            try:
                _ENGINE.dispose()
            except Exception:  # noqa: BLE001 - disposal must never mask the caller
                pass
        _ENGINE = None
        _ENGINE_KEY = None


def connect() -> Any:
    """A live connection to the backend app.db chose.

    SQLite hands back a DB-API connection (PRAGMA-readable); Postgres hands
    back a SQLAlchemy connection. Neither creates schema -- migrations own
    the schema, not connect time.
    """
    backend = backend_name()
    if backend == "sqlite":
        path = sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0, check_same_thread=False)
        conn.execute(SQLITE_BUSY_TIMEOUT_SQL)
        conn.execute(SQLITE_SYNCHRONOUS_SQL)
        return conn
    return engine().connect()
