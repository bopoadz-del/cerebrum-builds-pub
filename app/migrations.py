"""Apply and roll back Alembic revisions for this platform.

Deploy (scripts/entrypoint.sh) and the FastAPI lifespan both call
upgrade_head() against whichever engine app.db resolves. Failure refuses boot.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db import is_postgres, resolved_url, sqlite_path

ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", resolved_url())
    return cfg


def upgrade_head() -> str | None:
    command.upgrade(alembic_config(), "head")
    # Set WAL once, here, single-threaded, before the app serves any
    # request. WAL is a property of the file, so later connections inherit
    # it without switching journal mode (that race raises 'database is
    # locked' under the threadpool). Postgres has no journal mode.
    if not is_postgres():
        import sqlite3

        conn = sqlite3.connect(str(sqlite_path()))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()
        finally:
            conn.close()
    return current_revision()


def upgrade_to(revision: str) -> str | None:
    command.upgrade(alembic_config(), revision)
    return current_revision()


def downgrade(revision: str) -> str | None:
    command.downgrade(alembic_config(), revision)
    return current_revision()


def current_revision() -> str | None:
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
        return None
    finally:
        engine.dispose()


def head_revision() -> str | None:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(alembic_config()).get_current_head()
