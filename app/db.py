"""One place decides which database this platform runs on.

DATABASE_URL present means Postgres; absent means the SQLite file under
STORAGE_PATH. Both app.store and app.health ask this module, so the two can
never disagree about where the rows live.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

STORAGE_PATH_ENV = "STORAGE_PATH"
DATABASE_URL_ENV = "DATABASE_URL"
PLATFORM_DB_NAME = "platform.db"

#: How long SQLite waits for a write lock before answering "database is busy".
SQLITE_BUSY_TIMEOUT_MS = 30000
#: Bounded pool: save() never holds a connection while checking out another,
#: so the pool size is a concurrency budget, not a deadlock risk.
POOL_SIZE = 5
MAX_OVERFLOW = 10

_LOCK = threading.RLock()
_ENGINE: Engine | None = None
_ENGINE_KEY: tuple[str, str] | None = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORAGE_DIRNAME = "data"


def database_url() -> str:
    return (os.environ.get("DATABASE_URL") or "").strip()


def storage_root() -> Path:
    """The one persistence root: STORAGE_PATH, else the platform's own data
    directory beside the app (the same root either way, never a second one)."""
    raw = (os.environ.get("STORAGE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return ROOT / DEFAULT_STORAGE_DIRNAME


def sqlite_path() -> Path:
    return storage_root() / PLATFORM_DB_NAME


def backend_name() -> str:
    url = database_url()
    if not url:
        return "sqlite"
    scheme = url.split(":", 1)[0].lower()
    if scheme.startswith("postgres"):
        return "postgres"
    return "sqlite"


def resolved_url() -> str:
    url = database_url()
    if not url:
        root = storage_root()
        root.mkdir(parents=True, exist_ok=True)
        return "sqlite:///" + str(root / PLATFORM_DB_NAME)
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _build(url: str) -> Engine:
    kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": POOL_SIZE,
        "max_overflow": MAX_OVERFLOW,
        "pool_timeout": 60,
        "future": True,
    }
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0,
            "check_same_thread": False,
        }
    return create_engine(url, **kwargs)


def engine() -> Engine:
    """The one engine for the backend the environment names, rebuilt when the
    environment changes (a test may point STORAGE_PATH at a scratch disk)."""
    global _ENGINE, _ENGINE_KEY
    url = resolved_url()
    key = (backend_name(), url)
    with _LOCK:
        if _ENGINE is None or _ENGINE_KEY != key:
            if _ENGINE is not None:
                _ENGINE.dispose()
            _ENGINE = _build(url)
            _ENGINE_KEY = key
        return _ENGINE


def reset_engine() -> None:
    global _ENGINE, _ENGINE_KEY
    with _LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = None
        _ENGINE_KEY = None


def connect():
    """A DBAPI connection taken from the pool. Callers close it.

    app.health probes through this, and app.store takes its SQLAlchemy
    connection from :func:`engine`; neither opens a database of its own.
    """
    return engine().raw_connection()
