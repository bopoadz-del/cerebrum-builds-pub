"""Backup and restore for the SQLite persistence root.

A backup is not a backup until it restores: create_backup writes a consistent
copy through SQLite's own backup API, restore_backup puts it back, and
wipe_database removes the file the restore is drilled against.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app import db


def backup_root() -> Path:
    raw = (os.getenv("BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw)
    return Path(os.getenv("STORAGE_PATH") or ".") / "backups"


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("platform-*.db") if p.is_file())


def create_backup() -> Path:
    source = db.sqlite_path()
    if not source.is_file():
        raise FileNotFoundError("no database to back up at %s" % source)
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / ("platform-" + stamp + ".db")
    suffix = 1
    while target.exists():
        target = root / ("platform-" + stamp + "-" + str(suffix) + ".db")
        suffix += 1
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
    db.close_shared()
    path = db.sqlite_path()
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def restore_backup(archive: Path) -> None:
    db.close_shared()
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError("backup not found: %s" % archive)
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


def prune_backups(keep: int = 3) -> List[Path]:
    backups = list_backups()
    if keep < 0:
        keep = 0
    doomed = backups[:-keep] if keep else backups
    removed: List[Path] = []
    for path in doomed:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed.append(path)
    return removed
