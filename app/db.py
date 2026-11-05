"""The one place that decides which database this platform runs on.

DATABASE_URL present means PostgreSQL; absent means SQLite under
STORAGE_PATH. Nothing else in the application opens its own database, so
the two can never disagree.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL

_ENGINE: Engine | None = None
_BACKEND: str | None = None
_URL: str | None = None

SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("SQLITE_BUSY_TIMEOUT_MS", "10000"))

_DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data"


def _ensure_storage_default() -> None:
    """A local run with no STORAGE_PATH uses ./data; the image declares
    STORAGE_PATH=/data, and the operator's value always wins."""
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    if not raw:
        raw = str(_DEFAULT_ROOT)
        os.environ["STORAGE_PATH"] = raw
    try:
        Path(raw).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


_ensure_storage_default()


def storage_root() -> Path:
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    if not raw:
        # A missing STORAGE_PATH is a configuration error, not a silent
        # fallback to the current directory: the service must be told where
        # its persistent disk is.
        raise RuntimeError(
            "STORAGE_PATH is not set; the service needs a writable "
            "persistent directory before it can open its database"
        )
    return Path(raw)


def sqlite_path() -> Path:
    return storage_root() / "platform.db"


def database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return raw
    root = storage_root()
    root.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(root / "platform.db")


def backend_name() -> str:
    return "postgres" if (os.getenv("DATABASE_URL") or "").strip() else "sqlite"


def _make_engine() -> Engine:
    url = database_url()
    backend = backend_name()
    kwargs: Dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if backend == "sqlite":
        kwargs["connect_args"] = {"timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0}
        kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
        kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    else:
        kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
        kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    engine = create_engine(url, **kwargs)
    if backend == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return engine


def engine() -> Engine:
    """The one engine for the configured database.

    The URL is compared, not just the backend name: the lifecycle suite
    points STORAGE_PATH at a fresh directory per test, and a cached engine
    that ignored the new path would migrate one file while writing another.
    """
    global _ENGINE, _BACKEND, _URL
    backend = backend_name()
    url = database_url()
    if _ENGINE is None or _BACKEND != backend or _URL != url:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = _make_engine()
        _BACKEND = backend
        _URL = url
    return _ENGINE


def connect():
    """A connection on the live database.

    SQLite callers get the DBAPI connection (health and the lifecycle suite
    issue PRAGMA/SELECT text); PostgreSQL callers get a SQLAlchemy
    connection. Neither path creates schema -- Alembic owns that.
    """
    if backend_name() == "sqlite":
        import sqlite3

        path = sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # sqlite3's timeout is the busy timeout in seconds.
        return sqlite3.connect(str(path), timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0)
    return engine().connect()


def dispose() -> None:
    global _ENGINE, _BACKEND, _URL
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _BACKEND = None
    _URL = None


def url_object() -> URL:
    return engine().url
