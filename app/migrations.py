"""Alembic wrappers used by the boot path, /health and the lifecycle suite."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from app import db

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_LOCATION = ROOT / "alembic"


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", db.database_url())
    return cfg


def _prepare_sqlite() -> None:
    if db.backend_name() != "sqlite":
        return
    path = db.sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.commit()
    finally:
        conn.close()


def head_revision() -> Optional[str]:
    try:
        return ScriptDirectory.from_config(_config()).get_current_head()
    except Exception:  # noqa: BLE001 -- health reports the failure, never raises
        return None


def current_revision() -> Optional[str]:
    _prepare_sqlite()
    try:
        with db.get_engine().connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    except Exception:  # noqa: BLE001 -- health reports the failure, never raises
        return None


def upgrade_head() -> Optional[str]:
    _prepare_sqlite()
    command.upgrade(_config(), "head")
    return current_revision()


def upgrade_to(revision: str) -> Optional[str]:
    _prepare_sqlite()
    command.upgrade(_config(), revision)
    return current_revision()


def downgrade(revision: str) -> Optional[str]:
    _prepare_sqlite()
    command.downgrade(_config(), revision)
    return current_revision()
