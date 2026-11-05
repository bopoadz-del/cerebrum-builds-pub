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
from sqlalchemy.sql import ClauseElement

STORAGE_PATH_ENV = "STORAGE_PATH"
DATABASE_URL_ENV = "DATABASE_URL"
PLATFORM_DB_NAME = "platform.db"

#: How long SQLite waits for a write lock before answering "database is busy".
SQLITE_BUSY_TIMEOUT_MS = 30000
#: Bounded pool: save() never holds a connection while checking out another,
#: so the pool size is a concurrency budget, not a deadlock risk.
POOL_SIZE = 5
MAX_OVERFLOW = 10
#: SQLite admits one writer at a time. Several pooled connections racing for
#: that single writer make every commit bounce through the busy handler (and
#: on a network or overlay filesystem each retry is expensive), which starves
#: the pool under concurrent creates. One SQLite connection, serialised by the
#: pool, keeps the same concurrency guarantee without the busy-handler storm;
#: WAL still gives the file crash safety. Postgres keeps its larger pool.
SQLITE_POOL_SIZE = 1
SQLITE_MAX_OVERFLOW = 0

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
        "pool_timeout": 60,
        "future": True,
    }
    if url.startswith("sqlite"):
        kwargs["pool_size"] = SQLITE_POOL_SIZE
        kwargs["max_overflow"] = SQLITE_MAX_OVERFLOW
        kwargs["connect_args"] = {
            "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000.0,
            "check_same_thread": False,
        }
    else:
        kwargs["pool_size"] = POOL_SIZE
        kwargs["max_overflow"] = MAX_OVERFLOW
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


class CheckedConnection:
    """A driver connection that also accepts a SQLAlchemy clause.

    The shipped health probe hands Postgres a ``TextClause``. psycopg3
    adapts str, bytes and ``psycopg.sql.Composable`` only, so a raw driver
    connection rejects the clause. Compiling it here -- once, at the single
    connection entry point -- keeps /health truthful on the database the
    deployment actually runs. Strings and bytes pass through untouched.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, statement: Any, *args: Any, **kwargs: Any):
        if isinstance(statement, ClauseElement):
            try:
                statement = str(
                    statement.compile(compile_kwargs={"literal_binds": True})
                )
            except Exception:  # noqa: BLE001 -- str() is the portable form
                statement = str(statement)
        return self._conn.execute(statement, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __enter__(self) -> "CheckedConnection":
        self._conn.__enter__()
        return self

    def __exit__(self, *exc_info: Any) -> Any:
        return self._conn.__exit__(*exc_info)


def connect():
    """A DBAPI connection taken from the pool. Callers close it.

    app.health probes through this, and app.store takes its SQLAlchemy
    connection from :func:`engine`; neither opens a database of its own.
    SQLite is handed back exactly as the driver returns it; a server
    database is wrapped so a SQLAlchemy clause reaches it as SQL text.
    """
    conn = engine().raw_connection()
    if backend_name() == "sqlite":
        return conn
    return CheckedConnection(conn)
