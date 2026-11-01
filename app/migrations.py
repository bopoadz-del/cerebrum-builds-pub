"""Apply and roll back Alembic revisions for this platform.

Deploy (scripts/entrypoint.sh) and FastAPI lifespan both call
upgrade_head() against whichever engine app.db resolves. Failure
refuses boot.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

# app.db, never app.store: store.py is writer-authored, so what its
# connect() returns is not this module's to assume -- assuming sqlite3
# is how a SQLAlchemy connection met a raw string and every build with
# DATABASE_URL set died (ObjectNotExecutableError, 2026-09-27).
from app.db import is_postgres, resolved_url, sqlite_path

ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def upgrade_head() -> str | None:
    command.upgrade(alembic_config(), "head")
    # Set WAL once, here, single-threaded, before the app serves any
    # request -- so no connection under load has to switch journal mode
    # (that race raised 'database is locked'). Done inline, not through
    # app.store: store.py is writer-authored and only has to route
    # through app.db, so it may not expose a WAL helper. sqlite only;
    # Postgres has no journal mode to set.
    if not is_postgres():
        import sqlite3
        _c = sqlite3.connect(str(sqlite_path()))
        try:
            _c.execute("PRAGMA journal_mode=WAL")
        finally:
            _c.close()
    return current_revision()


def upgrade_to(revision: str) -> str | None:
    command.upgrade(alembic_config(), revision)
    return current_revision()


def downgrade(revision: str) -> str | None:
    command.downgrade(alembic_config(), revision)
    return current_revision()


def current_revision() -> str | None:
    # One code path for both engines: a short-lived SQLAlchemy engine
    # on the same URL alembic itself uses. The sqlite existence check
    # stays -- connecting through SQLAlchemy CREATES the file, and an
    # empty database appearing because someone asked "which revision?"
    # is a side effect nobody ordered.
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DatabaseError

    if not is_postgres() and not sqlite_path().exists():
        return None
    engine = create_engine(resolved_url())
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchone()
            return str(row[0]) if row else None
    except DatabaseError:
        # No alembic_version table yet: not migrated, not an error.
        return None
    finally:
        engine.dispose()


def head_revision() -> str | None:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(alembic_config()).get_current_head()
