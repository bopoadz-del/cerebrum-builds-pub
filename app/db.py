"""Where this platform's database connection comes from.

DATABASE_URL set means Postgres; absent means a SQLite file under
STORAGE_PATH. One place decides, so the two cannot disagree.

app/store.py obtains every connection from here. WAL is a persistent
property of the SQLite file and is switched once at boot by
app.migrations.upgrade_head(); it is NOT switched per connection.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

SQLITE_BUSY_TIMEOUT_MS = 30000
SQLITE_CONNECT_TIMEOUT_S = 30.0
_BUSY_TIMEOUT_PRAGMA = "PRAGMA busy_timeout=30000"

_ENGINE: Optional[Any] = None


def database_url() -> str:
    """The operator's choice, or empty for the SQLite development default."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    for bare in ("postgres://", "postgresql://"):
        if url.startswith(bare):
            return "postgresql+psycopg://" + url[len(bare):]
    return url


def is_postgres() -> bool:
    return bool(database_url())


def sqlite_path() -> Path:
    root = Path(os.environ.get("STORAGE_PATH", "./data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "platform.db"


def engine() -> Any:
    """The SQLAlchemy engine for DATABASE_URL. Raises when there is none."""
    global _ENGINE
    url = database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set; this platform is on SQLite at "
            f"{sqlite_path()}. Use connect() for a connection that works on "
            "either backend."
        )
    if _ENGINE is None:
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:  # pragma: no cover - deploy-time failure
            raise RuntimeError(
                "DATABASE_URL is set but SQLAlchemy is not installed."
            ) from exc
        _ENGINE = create_engine(
            url,
            pool_pre_ping=True,
            future=True,
            pool_size=5,
            max_overflow=10,
        )
    return _ENGINE


def connect() -> Any:
    """A live connection on whichever backend is configured."""
    if is_postgres():
        return engine().connect()
    conn = sqlite3.connect(
        str(sqlite_path()),
        timeout=SQLITE_CONNECT_TIMEOUT_S,
        check_same_thread=False,
        isolation_level="DEFERRED",
    )
    conn.row_factory = sqlite3.Row
    conn.execute(_BUSY_TIMEOUT_PRAGMA)
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def backend_name() -> str:
    return "postgres" if is_postgres() else "sqlite"


def resolved_url() -> str:
    """The one URL alembic and the health probe both read."""
    url = database_url()
    if url:
        return url
    path = sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + path.resolve().as_posix()
