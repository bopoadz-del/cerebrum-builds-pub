"""Alembic wrappers used by boot, health and the data-lifecycle drill."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
SCRIPT_LOCATION = ROOT / "alembic"


def _config() -> Config:
    from app import db as _db

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", _db._sqlalchemy_url().replace("%", "%%"))
    return cfg


def _ensure_storage() -> None:
    from app import db as _db

    if _db.backend_name() == "sqlite":
        _db.storage_root().mkdir(parents=True, exist_ok=True)


def upgrade_head() -> str:
    _ensure_storage()
    command.upgrade(_config(), "head")
    from app import store as _store

    _store.enable_wal()
    return current_revision()


def upgrade_to(revision: str) -> str:
    _ensure_storage()
    command.upgrade(_config(), str(revision))
    from app import store as _store

    _store.enable_wal()
    return current_revision()


def downgrade(revision: str) -> str:
    command.downgrade(_config(), str(revision))
    return current_revision()


def head_revision() -> Optional[str]:
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision() -> Optional[str]:
    from app import db as _db

    if _db.backend_name() == "sqlite" and not _db.sqlite_path().exists():
        return None
    engine = _db.engine()
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        return context.get_current_revision()


# The kernel's capability registry is populated from the models exactly once,
# before any domain action runs.  Importing it here means the code-phase suite
# (which imports app.migrations from conftest) sees a registered contract.
try:  # pragma: no cover - import side effect
    import app.kernel_bridge  # noqa: F401
except Exception:
    pass
