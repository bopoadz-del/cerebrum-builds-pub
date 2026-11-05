"""Backup, wipe and restore for the persistence root.

A backup nobody has restored is a file, not a backup: create_backup() writes
a SQLite backup of the live database and restore_backup() puts the rows back
into an empty root.
"""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
from pathlib import Path
from typing import List

from app import db as app_db
from app import store

BACKUP_DIR_ENV = "BACKUP_DIR"
BACKUP_PREFIX = "platform-"
BACKUP_SUFFIX = ".db"


def backup_root() -> Path:
    raw = (os.environ.get(BACKUP_DIR_ENV) or "").strip()
    if raw:
        return Path(raw)
    return app_db.storage_root() / "backups"


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(root.glob(BACKUP_PREFIX + "*" + BACKUP_SUFFIX))


def _stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup() -> Path:
    """Write a consistent copy of the SQLite database into the backup root."""
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{BACKUP_PREFIX}{_stamp()}{BACKUP_SUFFIX}"
    source_path = store.db_path()
    if app_db.backend_name() != "sqlite" or not source_path.exists():
        target.write_bytes(b"")
        return target
    source = sqlite3.connect(str(source_path))
    try:
        destination = sqlite3.connect(str(target))
        try:
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
    finally:
        source.close()
    return target


def wipe_database() -> None:
    """Remove the live database file (the backup still exists)."""
    path = store.db_path()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()
    app_db.reset_engine()


def restore_backup(archive: Path) -> Path:
    """Copy a backup back into the live root, then migrate to head."""
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(f"backup not found: {archive}")
    destination = store.db_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(archive.read_bytes())
    app_db.reset_engine()
    from app import migrations

    migrations.upgrade_head()
    return destination


def prune_backups(keep: int = 7) -> List[Path]:
    """Keep the newest ``keep`` backups; delete the rest."""
    backups = list_backups()
    if keep < 0:
        keep = 0
    stale = backups[: max(0, len(backups) - keep)]
    removed: List[Path] = []
    for path in stale:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed
