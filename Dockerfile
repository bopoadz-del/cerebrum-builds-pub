# Cerebrum Executive Programs
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/data \
    PORT=8000

WORKDIR /app

# Runtime dependencies only, against the Factory-owned pins. Nothing in this
# image runs the test suite: tests run in CI, not at build time.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The product tree: app, vendor (locked blocks), tracks, kits, alembic, docs.
COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data /data/exports /data/backups \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["sh", "scripts/entrypoint.sh"]
