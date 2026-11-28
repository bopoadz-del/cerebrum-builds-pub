#!/bin/sh
set -eu
python - <<'PY'
from app.backup import create_backup, prune_backups
archive = create_backup()
removed = prune_backups(keep=7)
print("backup:", archive)
for path in removed:
    print("pruned:", path)
PY
