# Cerebrum Executive Programs -- runtime image.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/data

WORKDIR /srv

# Runtime requirements only, resolved against the Factory's constraints.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The product tree: app/, alembic/, docs/, kits/, vendor/ (sealed blocks), UI.
COPY . .

# The persistence root exists, owned by the service user, before it switches.
RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /srv
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Migrations run at start-up (app.main lifespan), so a fresh volume boots ready.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
