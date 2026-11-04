"""Alembic runtime environment.

The URL comes from the alembic Config, which app.migrations fills from
app.db, so the migration always targets the same database the platform
serves: DATABASE_URL when present, STORAGE_PATH/platform.db otherwise.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The CLI path (scripts/entrypoint.sh runs ``python -m alembic upgrade head``)
# carries no URL of its own: take the one app.db decides, so the migration and
# the serving process always target the same database.
if not config.get_main_option("sqlalchemy.url"):
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    from app import db as _app_db

    config.set_main_option(
        "sqlalchemy.url", _app_db._sqlalchemy_url().replace("%", "%%")
    )

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
