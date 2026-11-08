# Harbourline Civil Works Contracts Administration.
# One image: the FastAPI service, its one served console (app/static/index.html),
# the alembic schema and the sealed vendor/ block tree. Tests never run here.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/app/data \
    PORT=8000

WORKDIR /app

# Runtime requirements only, resolved against the Factory-owned pins.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The product tree, including app/, alembic/, corpus/, kits/ and the sealed
# vendor/ block tree the app loads at run time.
COPY . .

# The service never needs root: the data volume is created and owned by the
# user the service runs as before it switches to it.
RUN useradd --system --uid 10001 --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/data \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Fail-closed health: the shipped app/health.py probes process, disk,
# database and migration head.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health', timeout=4)"

# scripts/entrypoint.sh applies the migration chain against the persistent
# disk and refuses to serve a schema behind head.
CMD ["sh", "scripts/entrypoint.sh"]
