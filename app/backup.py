"""Backup, restore and retention for the persistence root."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app import db


class BackupUnsupported(RuntimeError):
    """A byte-level backup is a SQLite facility; Postgres backups are pg_dump's."""


def backup_root() -> Path:
    raw = (os.getenv("BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw)
    return db.sqlite_path().parent / "backups"


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(root.glob("platform-*.db"))


def create_backup() -> Path:
    if db.backend_name() != "sqlite":
        raise BackupUnsupported("backup is implemented for the SQLite backend")
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / ("platform-%s.db" % stamp)
    source = db.sqlite_path()
    source.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


def wipe_database() -> None:
    path = db.sqlite_path()
    db.reset_engine()
    for candidate in (path, path.with_suffix(path.suffix + "-wal"), path.with_suffix(path.suffix + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def restore_backup(archive: Path) -> Path:
    target = db.sqlite_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(archive))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    db.reset_engine()
    return target


def prune_backups(keep: int = 7) -> List[Path]:
    backups = list_backups()
    if keep < 0:
        keep = 0
    doomed = backups[:-keep] if keep else backups
    removed: List[Path] = []
    for path in doomed:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed
