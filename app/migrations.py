"""Alembic wrappers used by the boot path, the data drills and health.

The database URL comes from app.db, so migrations and the store always
target the same database.  WAL is enabled once after every upgrade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app import db, store

ROOT = Path(__file__).resolve().parents[1]


def _url() -> str:
    if db.backend_name() == "postgres":
        url = db.database_url()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    return "sqlite:///" + str(db.sqlite_path())


def config() -> Config:
    if db.backend_name() == "sqlite":
        db.sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _url())
    return cfg


def upgrade_head() -> str:
    command.upgrade(config(), "head")
    store.enable_wal()
    return current_revision() or "head"


def upgrade_to(revision: str) -> str:
    command.upgrade(config(), revision)
    store.enable_wal()
    return revision


def downgrade(revision: str) -> str:
    command.downgrade(config(), revision)
    store.enable_wal()
    return revision


def current_revision() -> Optional[str]:
    conn = db.connect()
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except Exception:
        return None
    finally:
        conn.close()
    if row is None:
        return None
    try:
        return row[0]
    except (KeyError, IndexError, TypeError):
        return None


def head_revision() -> str:
    script = ScriptDirectory.from_config(config())
    return str(script.get_current_head() or "")
