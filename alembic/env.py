"""Alembic environment for the Delivery Service Platform.

The database URL is resolved the same way the application resolves it --
``DATABASE_URL`` when set, otherwise the SQLite file under ``STORAGE_PATH`` --
so a migration and the store can never disagree about where the data lives.
The parent directory of the SQLite file is created here because the boot step
(``python -m alembic upgrade head``) runs before the application does.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = None


def _database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url
    root = (os.getenv("STORAGE_PATH") or ".").strip() or "."
    path = Path(root) / "platform.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(path.resolve())


# ``%`` is an interpolation character in an alembic URL; escape it.
config.set_main_option("sqlalchemy.url", _database_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
