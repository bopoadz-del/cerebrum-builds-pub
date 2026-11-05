"""Backup and restore for the SQLite deployment.

A backup nobody restored is a file, not a backup: ``restore`` verifies the
copy opens and its schema is readable before replacing the live database.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app import db as app_db


def backup_dir() -> Path:
    raw = (os.getenv("BACKUP_DIR") or "").strip()
    root = Path(raw) if raw else app_db.storage_root() / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def backup(destination: Optional[str] = None) -> Path:
    source = app_db.sqlite_path()
    if not source.is_file():
        raise FileNotFoundError("no database to back up at %s" % source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = Path(destination) if destination else backup_dir() / ("platform-%s.db" % stamp)
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source))
    try:
        target_conn = sqlite3.connect(str(target))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()
    return target


def restore(backup_path: str) -> Path:
    candidate = Path(backup_path)
    if not candidate.is_file():
        raise FileNotFoundError(str(candidate))
    check = sqlite3.connect(str(candidate))
    try:
        tables = check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if not tables:
            raise ValueError("backup has no tables")
    finally:
        check.close()
    target = app_db.sqlite_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, target)
    return target


def prune(keep: int = 10) -> List[str]:
    files = sorted(backup_dir().glob("platform-*.db"), reverse=True)
    removed = []
    for path in files[max(0, int(keep)):]:
        try:
            path.unlink()
            removed.append(str(path))
        except OSError:
            continue
    return removed


def create_backup(destination: Optional[str] = None) -> Path:
    """The lifecycle suite's name for a verified SQLite snapshot."""
    return backup(destination)


def wipe_database() -> bool:
    """Remove the live SQLite file (and its WAL/SHM companions)."""
    path = app_db.sqlite_path()
    removed = False
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
            removed = True
        except FileNotFoundError:
            continue
    return removed


def restore_backup(backup_path: str) -> Path:
    """Restore a snapshot over the live database."""
    return restore(backup_path)


def backup_root() -> Path:
    return backup_dir()


def list_backups() -> List[Path]:
    return sorted(backup_dir().glob("platform-*.db"))


def prune_backups(keep: int = 10) -> List[str]:
    return prune(keep=keep)
