"""SQLite backup and restore drills over the one persistence root."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

DEFAULT_KEEP = 5


def backup_root() -> Path:
    raw = (os.environ.get("BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw)
    from app import db

    return db.storage_root() / "backups"


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("platform-*.db") if p.is_file())


def create_backup() -> Path:
    from app import db

    source = Path(db.sqlite_path())
    if not source.is_file():
        raise FileNotFoundError(str(source))
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / ("platform-" + stamp + ".db")
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    return target


def wipe_database() -> None:
    from app import db

    path = Path(db.sqlite_path())
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def restore_backup(archive: Path) -> Path:
    from app import db

    source = Path(archive)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    target = Path(db.sqlite_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("-wal", "-shm"):
        try:
            Path(str(target) + suffix).unlink()
        except FileNotFoundError:
            pass
    shutil.copy2(str(source), str(target))
    return target


def prune_backups(keep: int = DEFAULT_KEEP) -> List[Path]:
    archives = list_backups()
    if keep < 0:
        keep = 0
    surplus = archives[:-keep] if keep else list(archives)
    for archive in surplus:
        try:
            archive.unlink()
        except FileNotFoundError:
            continue
    return surplus
