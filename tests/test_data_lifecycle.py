"""S10 data lifecycle — performed, not configured.

Schema up/down on a populated v1 DB, a restore drill (backup → wipe →
restore → assert rows), and parallel writes at the FastAPI sync threadpool
size. connect() must not CREATE TABLE.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from app import backup, store
from app.migrations import current_revision, downgrade, upgrade_head, upgrade_to

ENTITY = 'cost_price_movement_alerts'
SAMPLE = {'reference': 's10-row', 'status': 'open', 'alert_reference': 's10-row', 'part_number': 's10-row', 'supplier': 's10-row', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
#: Tenant the generated tests act as. Tenant-scoped store calls require
#: an explicit tenant — never a default (the tenancy module's rule).
TENANT = "test-tenant"
ENTITIES = ['cost_price_movement_alerts', 'document_grounded_qa', 'document_ingestion_from_m365_and_upload', 'document_revision_nudges', 'manager_dashboard', 'manager_only_access', 'sap_odata_connector', 'supplier_cost_and_parts_pricing']
REV_V1 = '0001_baseline'
REV_V2 = '0002_lifecycle_audit'
AUDIT = 'lifecycle_audit'
#: The declared persistence contract (data_lifecycle.SQLITE_JOURNAL_MODE):
#: the journal mode the Factory's boot path sets. Asserted, never invented.
DECLARED_JOURNAL_MODE = 'wal'


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "data"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    return tmp_path


def _tables() -> set[str]:
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def test_connect_is_wal_with_a_busy_timeout_and_creates_nothing(isolated_db):
    """Observed on the connection and the module's syntax tree, not searched
    for in store.py's text. WAL is a property of the file: set by connect(),
    by a declared enable_wal(), or -- the Factory's own design -- once at
    boot by app.migrations.upgrade_head(), which says store.py (writer-
    authored) need not expose a WAL helper. All three are accepted; none
    may be missing. A connection by itself must never create a table."""
    import ast
    import inspect

    conn = store.connect()
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        made = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert int(timeout) > 0
    assert made == 0
    src = Path(inspect.getsourcefile(store)).read_text(encoding="utf-8")
    defs = {
        n.name for n in ast.walk(ast.parse(src))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if str(mode).lower() == DECLARED_JOURNAL_MODE or "enable_wal" in defs:
        return
    # The boot path owns WAL: after it runs, a fresh connection is WAL.
    upgrade_head()
    conn = store.connect()
    try:
        booted = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()
    assert str(booted).lower() == DECLARED_JOURNAL_MODE, (
        "WAL is set by none of connect(), app.store.enable_wal() or the "
        "boot path app.migrations.upgrade_head()"
    )


def test_connect_does_not_create_domain_tables(isolated_db):
    conn = store.connect()
    try:
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    for name in ENTITIES:
        assert name not in names, name


@pytest.mark.skipif(not ENTITY, reason="no domain entity to migrate")
def test_schema_change_applies_to_populated_v1_and_rolls_back(isolated_db):
    assert upgrade_to(REV_V1) == REV_V1
    saved = store.save(ENTITY, dict(SAMPLE), tenant_id=TENANT)
    assert saved["id"] is not None
    assert store.get(ENTITY, saved["id"], tenant_id=TENANT) is not None
    assert ENTITY in _tables()
    assert AUDIT not in _tables()

    # Upgrade to V2 explicitly, not to head: this test is about the
    # v1 -> v2 transition over populated data, and pinning the absolute
    # head would make the product unextendable -- any migration the
    # agent later authors for its own capability would fail this suite.
    assert upgrade_to(REV_V2) == REV_V2
    fetched = store.get(ENTITY, saved["id"], tenant_id=TENANT)
    assert fetched is not None, "v1 row did not survive upgrade to v2"
    for key, value in SAMPLE.items():
        assert fetched[key] == value
    assert AUDIT in _tables()
    assert current_revision() == REV_V2

    assert downgrade(REV_V1) == REV_V1
    rolled = store.get(ENTITY, saved["id"], tenant_id=TENANT)
    assert rolled is not None, "v1 row did not survive downgrade"
    for key, value in SAMPLE.items():
        assert rolled[key] == value
    assert AUDIT not in _tables()
    assert current_revision() == REV_V1


@pytest.mark.skipif(not ENTITY, reason="no domain entity to restore")
def test_restore_drill_backup_wipe_restore_rows(isolated_db):
    upgrade_head()
    original = [store.save(ENTITY, dict(SAMPLE), tenant_id=TENANT) for _ in range(3)]
    ids = [row["id"] for row in original]
    archive = backup.create_backup()
    assert archive.is_file() and archive.stat().st_size > 0

    backup.wipe_database()
    assert not store.db_path().exists()

    backup.restore_backup(archive)
    assert store.db_path().exists()
    restored_ids = [row["id"] for row in store.list_all(ENTITY, tenant_id=TENANT)]
    assert restored_ids == ids
    for row in original:
        fetched = store.get(ENTITY, row["id"], tenant_id=TENANT)
        assert fetched is not None
        for key, value in SAMPLE.items():
            assert fetched[key] == value


@pytest.mark.skipif(not ENTITY, reason="no domain entity to write")
def test_parallel_writes_match_fastapi_threadpool(isolated_db):
    upgrade_head()
    workers = store.FASTAPI_SYNC_THREADPOOL

    def _write(i: int):
        payload = dict(SAMPLE)
        if "reference" in payload:
            payload["reference"] = f"s10-{i}"
        return store.save(ENTITY, payload, tenant_id=TENANT)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_write, i) for i in range(workers)]
        results = [f.result() for f in as_completed(futures)]
    assert len(results) == workers
    assert all(r["id"] is not None for r in results)
    persisted = store.list_all(ENTITY, tenant_id=TENANT)
    assert len(persisted) == workers
    assert {r["id"] for r in persisted} == {r["id"] for r in results}


def test_wal_and_busy_timeout_after_migrate(isolated_db):
    upgrade_head()
    conn = store.connect()
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    finally:
        conn.close()
    assert str(mode).lower() == DECLARED_JOURNAL_MODE
    assert int(timeout) >= store.SQLITE_BUSY_TIMEOUT_MS


def test_retention_prunes_old_backups(isolated_db):
    upgrade_head()
    store.save(ENTITY, dict(SAMPLE), tenant_id=TENANT) if ENTITY else None
    root = backup.backup_root()
    root.mkdir(parents=True, exist_ok=True)
    for i in range(6):
        (root / f"platform-2026080{i}T000000Z.db").write_bytes(b"stub")
    removed = backup.prune_backups(keep=3)
    remaining = sorted(p.name for p in backup.list_backups() if p.stat().st_size == 4)
    assert len(removed) == 3
    assert remaining == [
        "platform-20260803T000000Z.db",
        "platform-20260804T000000Z.db",
        "platform-20260805T000000Z.db",
    ]
