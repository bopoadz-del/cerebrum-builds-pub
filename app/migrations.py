"""Alembic wrappers the boot path and the drills call.

Schema is migration-owned: ``upgrade_head()`` runs the revision chain, and the
one thing connect() never does is create a table. The boot path also switches
the SQLite file to WAL once -- not per connection, which races into
'database is locked' under the write drill.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import db

ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db.database_url().replace("%", "%%"))
    return cfg


def enable_wal() -> Optional[str]:
    """Switch the SQLite file to WAL once at boot. No-op on Postgres."""
    if db.backend_name() != "sqlite":
        return None
    conn = db.connect()
    try:
        row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        conn.execute("PRAGMA synchronous=NORMAL")
        return str(row[0]).lower() if row else None
    finally:
        conn.close()


def upgrade_head() -> str:
    enable_wal()
    command.upgrade(alembic_config(), "head")
    return current_revision() or ""


def upgrade_to(revision: str) -> str:
    enable_wal()
    command.upgrade(alembic_config(), revision)
    return current_revision() or ""


def downgrade(revision: str) -> str:
    command.downgrade(alembic_config(), revision)
    return current_revision() or ""


def stamp(revision: str) -> str:
    command.stamp(alembic_config(), revision)
    return current_revision() or ""


def current_revision() -> Optional[str]:
    conn = db.connect()
    try:
        if db.backend_name() != "sqlite":
            from sqlalchemy import text as _sql_text

            row = conn.execute(_sql_text("SELECT version_num FROM alembic_version")).fetchone()
        else:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except Exception:  # noqa: BLE001 - no revision table yet is a real answer
        return None
    finally:
        conn.close()
    return str(row[0]) if row else None


def head_revision() -> Optional[str]:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def revision_of(connection) -> Optional[str]:
    return MigrationContext.configure(connection).get_current_revision()
