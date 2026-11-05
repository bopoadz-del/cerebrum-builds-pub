"""Alembic wrappers: the schema is versioned, never created at boot.

upgrade_head() runs the revisions and switches the SQLite file to WAL once;
connect() itself never issues DDL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app import db as app_db

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = ROOT / "alembic"
ALEMBIC_INI = ROOT / "alembic.ini"


def _config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", app_db.resolved_url().replace("%", "%%"))
    return cfg


def head_revision() -> Optional[str]:
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision() -> Optional[str]:
    engine = app_db.engine()
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _switch_sqlite_to_wal() -> None:
    if app_db.backend_name() != "sqlite":
        return
    conn = app_db.connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def upgrade_to(revision: str) -> str:
    command.upgrade(_config(), revision)
    _switch_sqlite_to_wal()
    return current_revision() or revision


def upgrade_head() -> str:
    command.upgrade(_config(), "head")
    _switch_sqlite_to_wal()
    return current_revision() or ""


def downgrade(revision: str) -> str:
    command.downgrade(_config(), revision)
    return current_revision() or ""


def ensure_schema() -> str:
    """Boot path: apply every revision. Idempotent."""
    return upgrade_head()
