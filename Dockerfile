FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STORAGE_PATH=/data \
    PORT=8000

WORKDIR /app

# Runtime dependencies only, resolved against the Factory's pinned
# constraints so every image build gets the same framework versions.
COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The product tree, including the sealed vendor/blocks the app loads from
# their locked paths. COPY . . keeps vendor/, frontend/ and kits/ in the image.
COPY . .

# The locked blocks are loaded from vendor/blocks at run time. A merge that
# drops that sealed tree would boot a 200-but-dead product, so the image
# refuses to build without it.
RUN test -d /app/vendor/blocks || (echo "vendor/blocks missing from the merged tree" >&2; exit 1)

RUN useradd --create-home --uid 10001 platform \
    && mkdir -p "$STORAGE_PATH" \
    && chown -R platform:platform "$STORAGE_PATH" /app \
    && chmod +x /app/scripts/entrypoint.sh 2>/dev/null || true

USER platform

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=4)"

CMD ["sh", "/app/scripts/entrypoint.sh"]
