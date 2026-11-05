# syntax=docker/dockerfile:1
#
# Harbourline Civil Works Contracts Administration Platform
#
# The runtime image carries the whole merged product tree: app/ (the ASGI app,
# its routes, capability actions and alembic wrappers), alembic/ (the versioned
# schema), docs/ (the uploaded contract excerpt and the priced BOQ every record
# is grounded in) and vendor/ (the locked Store blocks each capability
# dispatches to). vendor/ must NOT be excluded: app/dispatch.py loads a block by
# path from vendor/blocks/<id>/block.py and refuses a missing one at start-up.
#
# Nothing at build time runs the tests or the release gate.

FROM python:3.11-slim

# No bytecode beside the sources, unbuffered logs (the request log is one JSON
# object per line), and no pip cache left in the layer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# The pin table first: constraints.txt holds every locked distribution version,
# requirements.txt declares what this runtime needs and repeats no pin. Copying
# both before the tree keeps a source change from re-resolving the stack.
COPY constraints.txt requirements.txt ./
RUN pip install -c constraints.txt -r requirements.txt

# The merged tree, including vendor/ (the Store blocks) and docs/ (the contract
# excerpt and the BOQ). No tests and no release gate run here: the image is
# built to serve, and /health states the truth once the process is up.
COPY . .

# Unprivileged runtime user. /data is created owned by appuser BEFORE USER, so
# a volume mounted there is writable without root: STORAGE_PATH holds the
# SQLite database, work/ and the backups.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
 && mkdir -p /data \
 && chown appuser:appuser /data

USER appuser

# Declared, not defaulted in code (app/config.py, app/db.py): a deploy must be
# able to mount a volume on /data and reach the Store gate's declared settings.
ENV STORAGE_PATH=/data \
    PORT=8000

EXPOSE 8000

# A 200 means this process serves, STORAGE_PATH is a writable directory, the
# configured database answers and alembic is at head (app/health.py). Anything
# else is a 503, and this probe reports the container unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health',timeout=4).status==200 else 1)"

# Apply the alembic head, then serve. upgrade_head() is idempotent (and the
# app's own lifespan applies it again), so a restart is safe.
CMD ["sh", "-c", "python -c \"from app.migrations import upgrade_head; upgrade_head()\" && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
