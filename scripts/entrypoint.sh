#!/bin/sh
# Boot the platform. Alembic upgrade runs in the app lifespan before serving.
set -eu
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
