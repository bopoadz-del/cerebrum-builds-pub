"""Backup, wipe and restore for the platform's persistence root.

A backup nobody restored is a file.  ``create_backup`` copies the live
database through SQLite's own backup API, ``wipe_database`` removes it, and
``restore_backup`` puts it back -- the drill the lifecycle suite performs.
The PostgreSQL backend is refused here rather than half-supported: the
operator's database backup is their DBA's procedure, not a file copy.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

BACKUP_DIR_ENV = "BACKUP_DIR"
KEEP_DEFAULT = 3


class BackupUnsupported(RuntimeError):
    """The configured backend is not a file this module can copy."""


def _db():
    from app import db

    return db


def backup_root() -> Path:
    raw = (os.environ.get(BACKUP_DIR_ENV) or "").strip()
    if raw:
        return Path(raw)
    return _db().storage_root() / "backups"


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("platform-*.db") if p.is_file())


def create_backup(label: str = "") -> Path:
    db = _db()
    if db.backend_name() != "sqlite":
        raise BackupUnsupported("file backups are defined for the SQLite backend")
    source = db.sqlite_path()
    if not source.exists():
        raise FileNotFoundError("no database to back up at %s" % source)
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = ("-" + label) if label else ""
    target = root / ("platform-%s%s.db" % (stamp, suffix))
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    return target


def wipe_database() -> None:
    db = _db()
    if db.backend_name() != "sqlite":
        raise BackupUnsupported("wiping a server database is not a file operation")
    path = db.sqlite_path()
    db.reset_engine()
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue


def restore_backup(archive: Path) -> Path:
    db = _db()
    if db.backend_name() != "sqlite":
        raise BackupUnsupported("restoring a server database is not a file operation")
    source = Path(archive)
    if not source.is_file():
        raise FileNotFoundError("no backup at %s" % source)
    target = db.sqlite_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    db.reset_engine()
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    return target


def prune_backups(keep: int = KEEP_DEFAULT) -> List[str]:
    """Delete the oldest archives beyond ``keep``; return the names removed."""
    keep = max(0, int(keep))
    archives = list_backups()
    doomed = archives[: max(0, len(archives) - keep)]
    removed: List[str] = []
    for path in doomed:
        try:
            path.unlink()
            removed.append(path.name)
        except FileNotFoundError:
            continue
    return removed


def status() -> Dict[str, object]:
    return {
        "backend": _db().backend_name(),
        "root": str(backup_root()),
        "archives": [p.name for p in list_backups()],
    }
