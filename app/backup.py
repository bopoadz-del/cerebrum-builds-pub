"""Backup and restore of the one persistence file.

A backup nobody has restored is a file, not a backup: restore_backup()
replaces the live database and the lifecycle suite reads the rows back.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app import db


def backup_root() -> Path:
    raw = (os.getenv("BACKUP_DIR") or "").strip()
    return Path(raw) if raw else db.storage_root() / "backups"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup() -> Path:
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"platform-{_stamp()}.db"
    source = db.sqlite_path()
    if db.backend_name() == "sqlite" and source.exists():
        src = sqlite3.connect(str(source))
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    else:
        raise RuntimeError("backup is supported for the SQLite persistence root only")
    return target


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(root.glob("platform-*.db"))


def prune_backups(keep: int = 3) -> List[Path]:
    backups = list_backups()
    doomed = backups[: max(0, len(backups) - max(1, int(keep)))]
    removed: List[Path] = []
    for path in doomed:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed


def wipe_database() -> None:
    path = db.sqlite_path()
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def restore_backup(archive: Path) -> Path:
    source = Path(archive)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    target = db.sqlite_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target
