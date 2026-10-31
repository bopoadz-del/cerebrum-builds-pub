"""The backup restores, with the rows still in it.

Written by the factory. The floor (backup_restore_roundtrip) refuses a
backup that has never been restored: dump, wipe, restore, and the planted
row must still be readable.
"""

import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "backup.sh"


def _posix_shell():
    """A bash that can actually run a POSIX script, or None.

    On Windows ``bash`` usually resolves to the WSL launcher. With no distro
    installed it answers "Windows Subsystem for Linux has no installed
    distributions." -- in UTF-16, which then arrives as mojibake in whatever
    captured it. Proving the shell works before using it is cheaper than
    decoding that twice.
    """
    found = shutil.which("bash")
    if not found:
        return None
    try:
        probe = subprocess.run(
            [found, "-c", "exit 0"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # The shell RAN when it exits 0 -- the launcher with no distro does not.
    return found if probe.returncode == 0 else None


@pytest.mark.skipif(
    bool(os.environ.get("DATABASE_URL")),
    reason="sqlite roundtrip; the Postgres leg runs in the gate against a server",
)
def test_a_backup_restores_with_its_rows(tmp_path):
    storage = tmp_path / "data"
    storage.mkdir()
    db = storage / "platform.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE planted (id TEXT PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO planted VALUES ('a1', 'survives the restore')")

    assert SCRIPT.is_file(), "scripts/backup.sh is missing"
    bash = _posix_shell()
    if bash is None:
        pytest.skip("no POSIX shell here; backup.sh is a shell script")
    env = dict(os.environ)
    env["STORAGE_PATH"] = str(storage)
    env["DATABASE_URL"] = ""
    if shutil.which("sqlite3") is None:
        pytest.skip("the sqlite3 CLI is not on this runner")
    out = subprocess.run(
        [bash, str(SCRIPT), str(tmp_path / "backups")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        errors="replace",
        env=env,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    printed = out.stdout.strip().splitlines()
    assert printed, "backup.sh printed no path"
    dump = Path(printed[-1])
    assert dump.is_file(), "backup.sh printed a path that is not a file"

    db.unlink()
    shutil.copy(dump, db)

    with sqlite3.connect(db) as conn:
        rows = list(conn.execute("SELECT note FROM planted WHERE id = 'a1'"))
    assert rows and rows[0][0] == "survives the restore", (
        "the restored database lost the planted row"
    )
