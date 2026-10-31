"""Backup, restore and retention for the single persistence root."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import List

from app import db as _db


def backup_root() -> Path:
    configured = (os.getenv("BACKUP_DIR") or "").strip()
    return Path(configured) if configured else _db.storage_root() / "backups"


def create_backup() -> Path:
    root = backup_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = root / f"platform-{stamp}.db"
    source = _db.sqlite_path()
    if not source.exists():
        raise FileNotFoundError(str(source))
    shutil.copy2(source, target)
    return target


def wipe_database() -> None:
    path = _db.sqlite_path()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()


def restore_backup(archive: Path) -> Path:
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(str(archive))
    target = _db.sqlite_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, target)
    return target


def list_backups() -> List[Path]:
    root = backup_root()
    if not root.is_dir():
        return []
    return sorted(root.glob("platform-*.db"))


def prune_backups(keep: int = 5) -> List[Path]:
    backups = list_backups()
    remove = backups[:-keep] if keep > 0 else backups
    for path in remove:
        try:
            path.unlink()
        except OSError:
            pass
    return remove
