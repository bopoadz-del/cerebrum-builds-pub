"""Alembic env for a generated platform. app.db decides the engine."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# The product root, so `app` imports when alembic is run as a bare CLI
# (scripts/entrypoint.sh) as well as through app/migrations.py.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# One place decides the engine. This file used to keep its own copy --
# "Must match app.store.db_path(). Duplicated so a migration can run
# before app is imported." -- and the copy hardcoded sqlite, so a
# platform with DATABASE_URL set migrated one database and served
# another. That is the exact failure the acceptance floor's own text
# forbids: a DATABASE_URL that is read and then ignored.
from app.db import resolved_url as sqlalchemy_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    context.configure(
        url=sqlalchemy_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(sqlalchemy_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
