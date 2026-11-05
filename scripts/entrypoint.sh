#!/bin/sh
# Boot the platform: apply versioned migrations to the persistent disk, then
# serve. A schema that cannot reach head refuses boot rather than serving with
# a half-migrated database.
set -eu

: "${PORT:=8000}"
: "${STORAGE_PATH:=/app/data}"

export STORAGE_PATH
mkdir -p "$STORAGE_PATH"

python -m alembic upgrade head

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
