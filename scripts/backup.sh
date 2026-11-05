#!/bin/sh
# Back up the SQLite persistence root. Run from the deployed image (cron-safe).
set -eu
python - <<'PY'
from app.backup import create_backup, prune_backups
print(create_backup())
print(len(prune_backups(keep=5)), "old backup(s) pruned")
PY
