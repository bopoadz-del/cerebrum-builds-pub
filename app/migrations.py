"""Alembic wrappers used by boot, health and the data-lifecycle suite."""

from __future__ import annotations

import threading
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

from app import db as _db

ROOT = Path(__file__).resolve().parents[1]
_LOCK = threading.Lock()


def config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _db.url().replace("%", "%%"))
    return cfg


def head_revision() -> str | None:
    return ScriptDirectory.from_config(config()).get_current_head()


def current_revision() -> str | None:
    engine = create_engine(_db.url(), poolclass=pool.NullPool, future=True)
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def upgrade_to(revision: str) -> str:
    with _LOCK:
        command.upgrade(config(), revision)
        _db.enable_wal()
    return revision


def upgrade_head() -> str | None:
    with _LOCK:
        command.upgrade(config(), "head")
        _db.enable_wal()
    return current_revision()


def downgrade(revision: str) -> str:
    with _LOCK:
        command.downgrade(config(), revision)
        _db.enable_wal()
    return revision
