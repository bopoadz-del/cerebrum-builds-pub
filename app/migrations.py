"""Alembic wrappers used by boot, health and the lifecycle suite."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def head_revision() -> str:
    return ScriptDirectory.from_config(config()).get_current_head()


def current_revision() -> Optional[str]:
    from app import db as app_db

    conn = app_db.engine().connect()
    try:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()
    finally:
        conn.close()


def upgrade_head() -> str:
    command.upgrade(config(), "head")
    from app.store import enable_wal

    enable_wal()
    return current_revision() or head_revision()


def upgrade_to(revision: str) -> str:
    """Upgrade to an explicit revision and return the revision reached.

    Returning the revision (not None) is the lifecycle suite's contract:
    it asks what was applied, not merely that the call did not raise.
    """
    command.upgrade(config(), str(revision))
    return current_revision() or str(revision)


def downgrade(revision: str) -> str:
    command.downgrade(config(), str(revision))
    return current_revision() or str(revision)
