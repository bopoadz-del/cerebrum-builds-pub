"""Alembic wrappers: the schema moves only through revisions.

upgrade_head() runs at boot (the FastAPI lifespan), sets WAL once on the
SQLite file, and is what /health compares the current revision against.
No CREATE TABLE happens at connect time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import db

_ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    cfg = Config(str(_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db.database_url())
    return cfg


def head_revision() -> Optional[str]:
    return ScriptDirectory.from_config(_config()).get_current_head()


def upgrade_head() -> str:
    command.upgrade(_config(), "head")
    db.enable_wal()
    return str(current_revision() or "")


def upgrade_to(revision: str) -> str:
    command.upgrade(_config(), revision)
    db.enable_wal()
    return str(current_revision() or "")


def downgrade(revision: str) -> str:
    command.downgrade(_config(), revision)
    return str(current_revision() or "")


def current_revision() -> Optional[str]:
    from sqlalchemy import create_engine

    engine = create_engine(db.database_url(), future=True)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()
