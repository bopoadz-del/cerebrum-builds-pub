# Harbourline Civil Works Contracts Administration — runtime image.
#
# Runtime dependencies only: migrations run on boot, tests run in CI, never
# during a build. The persistence root is a mounted volume at STORAGE_PATH;
# the image creates it owned by the service user before dropping privileges.
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/data \
    PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The framework stack is pinned once, in constraints.txt.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The product tree, including the sealed block slice under vendor/ and the
# kit packs under kits/ (the app loads locked blocks from vendor/blocks/<id>/).
COPY . .

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p "${STORAGE_PATH}" \
    && chown -R appuser:appuser "${STORAGE_PATH}" \
    && chmod +x scripts/entrypoint.sh scripts/backup.sh scripts/rollback.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"

# Migrations to head, then serve. A schema behind head refuses boot.
CMD ["./scripts/entrypoint.sh"]
