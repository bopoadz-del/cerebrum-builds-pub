from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:  # noqa: BLE001 -- a config without logging is valid
        pass

target_metadata = None


def _database_url() -> str:
    """The URL app.db decides, unless the caller already set one.

    app/migrations.py builds a Config with the URL pinned, so that path is
    unchanged. The CLI entrypoint (``python -m alembic upgrade head``) reads
    alembic.ini, which carries no URL: ask the one place that decides the
    backend rather than guessing a second database here.
    """
    configured = (config.get_main_option("sqlalchemy.url") or "").strip()
    if configured:
        return configured
    from app import db as app_db

    url = app_db.database_url()
    if app_db.backend_name() == "sqlite":
        app_db.sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    config.set_main_option("sqlalchemy.url", url)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _database_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
