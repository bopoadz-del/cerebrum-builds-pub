#!/bin/sh
set -eu
# Migrate against the persistent disk, then serve. A failed migration
# refuses boot: the platform never serves a schema it did not apply.
python -m alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
