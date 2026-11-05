# Harbourline Civil Works contracts administration -- runtime image.
#
# The image is the product tree: app/, alembic/, docs/, frontend/, scripts/,
# the sealed vendor/ blocks and the kits/ shelf. The Factory merges vendor/
# and kits/ into the build context; COPY . . picks them up unchanged.
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/app/data

WORKDIR /app

# Tesseract is the local OCR engine the sealed ocr block uses for a scanned
# image; the text-layer fallback needs no external service.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Runtime requirements only, resolved against the Factory's pins.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The merged product tree. .dockerignore must never exclude vendor/ or kits/.
COPY . .

# The one persistence root exists before the service drops privileges.
RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data /app
USER appuser

EXPOSE 8000

# Fail-closed: /health is 503 until process, disk, database and migration head
# all answer, so an unhealthy instance is taken out before it takes traffic.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# The entrypoint migrates to head, then serves; a schema that cannot reach
# head refuses boot instead of serving half-migrated.
CMD ["sh", "scripts/entrypoint.sh"]
