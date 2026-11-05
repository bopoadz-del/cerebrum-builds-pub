"""The Postgres path, measured without a Postgres server.

The Store gate boots the image against DATABASE_URL and asks /health. Two
things can only fail there and are cheap to pin here:

* the schema the baseline migration emits must be valid Postgres DDL, not
  SQLite DDL that happens to compile; and
* app.health hands a server database a SQLAlchemy ``TextClause``, which a
  raw psycopg connection cannot adapt -- app.db.connect() must present the
  clause as SQL text while leaving the SQLite connection untouched.
"""

from __future__ import annotations

import contextlib
import io

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app import db, health, migrations, models


class _RecordingConnection:
    """Stands in for a driver connection: records what execute() receives."""

    def __init__(self) -> None:
        self.statements = []
        self.closed = False

    def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return self

    def close(self) -> None:
        self.closed = True


def test_checked_connection_compiles_a_sqlalchemy_clause_to_sql_text():
    driver = _RecordingConnection()
    conn = db.CheckedConnection(driver)
    conn.execute(text("SELECT 1"))
    conn.execute("SELECT 1")
    assert driver.statements == ["SELECT 1", "SELECT 1"]
    conn.close()
    assert driver.closed


def test_health_probe_reaches_a_server_database_through_connect(monkeypatch):
    """backend_name() says Postgres (as it does under DATABASE_URL); the probe
    must not fail because the driver was handed a TextClause. The engine is
    still the local SQLite file, so the compiled text is the only thing that
    reaches the driver."""
    migrations.upgrade_head()
    monkeypatch.setattr(db, "backend_name", lambda: "postgres")
    code, body = health.evaluate_health()
    database = [c for c in body["checks"] if c["name"] == "database"]
    assert database and database[0]["ok"], body
    assert code == 200


def test_baseline_migration_emits_postgres_ddl_for_every_entity():
    cfg = Config(str(db.ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(db.ROOT / "alembic"))
    cfg.set_main_option(
        "sqlalchemy.url", "postgresql+psycopg://user:pass@localhost:5432/harbourline"
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        command.upgrade(cfg, "head", sql=True)
    ddl = out.getvalue()
    assert "CREATE TABLE" in ddl
    for entity in models.MODELS:
        assert "CREATE TABLE %s (" % entity in ddl, entity
    assert "CREATE TABLE lifecycle_audit (" in ddl
    assert "SERIAL" in ddl
