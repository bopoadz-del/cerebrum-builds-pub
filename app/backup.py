"""Backup, wipe and restore for the SQLite root.

A backup nobody has restored is a file, not a backup: the pair
``create_backup`` / ``restore_backup`` is exercised by the lifecycle drill
(backup -> wipe -> restore -> rows intact), and ``prune_backups`` keeps the
newest N by the timestamp in the file name so a rollback is bounded.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app import config, db

PREFIX = "platform-"
SUFFIX = ".db"
DEFAULT_KEEP = 7


def backup_root() -> Path:
    raw = (os.environ.get("BACKUP_DIR") or "").strip()
    if raw:
        return Path(raw)
    return config.storage_root() / "backups"


def list_backups(root: Optional[Path] = None) -> List[Path]:
    directory = root or backup_root()
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.glob(PREFIX + "*" + SUFFIX) if path.is_file()),
        key=lambda path: path.name,
    )


def create_backup(root: Optional[Path] = None) -> Path:
    """Copy the live database through SQLite's backup API (WAL-safe)."""
    if db.backend_name() != "sqlite":
        raise RuntimeError("file backups apply to the SQLite root; Postgres uses its own snapshots")
    source = db.sqlite_path()
    if not source.exists():
        raise FileNotFoundError(str(source))
    directory = root or backup_root()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = directory / (PREFIX + stamp + SUFFIX)
    source_conn = db.connect()
    try:
        target_conn = sqlite3.connect(str(target))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()
    return target


def wipe_database() -> None:
    """Remove the database file and its WAL sidecars (the drill's 'wipe')."""
    db.reset_engine()
    path = db.sqlite_path()
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue


def restore_backup(archive: Path) -> Path:
    """Replace the live database with ``archive``."""
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(str(archive))
    db.reset_engine()
    destination = db.sqlite_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    for sidecar in (Path(str(destination) + "-wal"), Path(str(destination) + "-shm")):
        try:
            sidecar.unlink()
        except FileNotFoundError:
            continue
    with open(archive, "rb") as source, open(destination, "wb") as target:
        target.write(source.read())
    db.reset_engine()
    return destination


def prune_backups(keep: int = DEFAULT_KEEP, root: Optional[Path] = None) -> List[Path]:
    """Delete all but the newest ``keep`` backups; return what was removed."""
    backups = list_backups(root)
    if keep < 0:
        keep = 0
    stale = backups[: max(0, len(backups) - keep)]
    removed: List[Path] = []
    for path in stale:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed.append(path)
    return removed
