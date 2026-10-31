"""Alembic wrappers used by the boot path, health and the lifecycle suite.

The schema lives in alembic revisions; nothing here creates a table with
metadata.create_all(). WAL is switched on once at boot for SQLite.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import db as _db

ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _db.database_url())
    return cfg


def _enable_wal() -> None:
    if _db.backend_name() != "sqlite":
        return
    try:
        _db.enable_wal()
    except Exception:
        # Health reports a database that cannot be prepared; boot still
        # raises from the migration itself when the schema cannot apply.
        pass


def upgrade_head() -> str:
    _enable_wal()
    command.upgrade(_config(), "head")
    return current_revision() or ""


def upgrade_to(revision: str) -> str:
    _enable_wal()
    command.upgrade(_config(), revision)
    return current_revision() or revision


def downgrade(revision: str) -> str:
    command.downgrade(_config(), revision)
    return current_revision() or revision


def current_revision() -> str:
    with _db.engine().connect() as conn:
        return MigrationContext.configure(conn).get_current_revision() or ""


def head_revision() -> str:
    return ScriptDirectory.from_config(_config()).get_current_head() or ""
