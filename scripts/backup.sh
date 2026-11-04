#!/usr/bin/env bash
# Take a backup of whatever this platform stores on.
#
#   DATABASE_URL set   -> pg_dump
#   DATABASE_URL unset -> sqlite3 .backup of STORAGE_PATH/platform.db
#
# Written by the factory. A backup nobody has restored is a file, not a
# backup: tests/test_backup_restore.py restores what this produces.
set -euo pipefail

OUT="${1:-./backups}"
mkdir -p "$OUT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if [ -n "${DATABASE_URL:-}" ]; then
  DEST="$OUT/platform-$STAMP.sql"
  pg_dump "$DATABASE_URL" > "$DEST"
else
  SRC="${STORAGE_PATH:-./data}/platform.db"
  DEST="$OUT/platform-$STAMP.db"
  if [ ! -f "$SRC" ]; then
    echo "no database at $SRC" >&2
    exit 1
  fi
  sqlite3 "$SRC" ".backup '$DEST'"
fi

echo "$DEST"
