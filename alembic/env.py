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

from app import db as _db  # noqa: E402

config = context.config
# The app's boot path (app.migrations.upgrade_head) runs after the product has
# installed its JSON request logging. Re-running alembic.ini's logging config
# there would replace that root handler with a stderr formatter and drop
# request lines. The CLI (no app imported) keeps its own configuration.
if config.config_file_name is not None and "app.observe" not in sys.modules:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None


def _url() -> str:
    return _db.database_url()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    if _db.backend_name() == "sqlite":
        # WAL is a property of the file and does not need the migration's
        # transaction; a PRAGMA inside it would keep the version insert open.
        _db.enable_wal()
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
