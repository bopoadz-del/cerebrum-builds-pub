# Harbourline Civil Works contracts administration.
#
# The image is built from the merged product tree, so it carries vendor/
# (the locked Store blocks) and kits/ (their packs) exactly as shipped.
# Only runtime requirements are installed -- tests run in CI, never here.

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/app/data \
    PORT=8000

WORKDIR /app

# Dependencies first: the layer is reusable while the source moves.
COPY constraints.txt requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -c constraints.txt -r requirements.txt

# The product tree: app/, vendor/, kits/, alembic/, scripts/, docs/.
COPY . .

# The persistence root the service writes to. It exists in the image and is
# owned by the runtime user, so a fresh volume mounted here starts writable
# and the service never needs root for its own data.
RUN useradd --create-home --uid 10001 platform \
    && mkdir -p "$STORAGE_PATH" \
    && chown -R platform:platform /app "$STORAGE_PATH" \
    && chmod +x scripts/entrypoint.sh

USER platform

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT','8000'), timeout=4); sys.exit(0 if r.status == 200 else 1)"

# Apply migrations against the persistent disk, then serve. The entrypoint
# is fail-closed: a schema behind head refuses boot.
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
