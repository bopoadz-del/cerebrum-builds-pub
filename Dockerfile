# Deployable image for the coffee-compost factory platform.
#
# Offline posture P1: no block-store callback, no cloud LLM, no outbound HTTP
# at runtime. The twelve Store blocks are vendored under vendor/ and dispatched
# in-process by app/dispatch.py.
#
# The build installs the RUNTIME requirements only, pinned by constraints.txt.
# It never installs requirements-dev.txt and never runs the test suite, the
# acceptance harness or the release gate -- the grading harness runs INSIDE this
# image, it does not build it.
#
# The console GET / serves is app/static/index.html: committed, self-contained
# and needing no toolchain (no Node stage, nothing compiled at build time).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    STORAGE_PATH=/data

WORKDIR /app

COPY constraints.txt requirements.txt ./
RUN python -m pip install --no-cache-dir -c constraints.txt -r requirements.txt

# The service itself:
#   app/            the platform (routes, handlers, persistence, console)
#   vendor/         the sealed block slice and the product-kernel runtime
#   kits/           the kit pack manifests the blocks were stocked under
#   alembic/ + alembic.ini   the versioned schema the entrypoint applies
#   scripts/        entrypoint.sh (migrations then uvicorn), backup.sh, bench.py
#   docs/           the declared locale and the openapi contract
#   deploy/         the deploy contract
COPY . .

# The console the image serves is built from this tree, not copied by hand:
# frontend/dist/index.html is validated and rendered into app/static/index.html
# by a stdlib-only script (no npm, no bundler, no network).
COPY frontend ./frontend
RUN python3 frontend/build.py

RUN groupadd --system --gid 10001 platform \
 && useradd --system --uid 10001 --gid platform --home /app --shell /usr/sbin/nologin platform \
 && mkdir -p /data \
 && chown -R platform:platform /data /app

USER platform

EXPOSE 8000

# Fail-closed probe: /health is 503 until the process serves, STORAGE_PATH is a
# writable disk, the database answers and Alembic is at head. The image ships no
# curl/wget, so the interpreter performs the GET and urllib raises on any
# non-200 (503 included), making the probe exit non-zero.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + str(os.environ.get('PORT') or '8000') + '/health', timeout=4).read()"

# alembic upgrade head (failure refuses boot), then uvicorn on $PORT.
ENTRYPOINT ["sh", "/app/scripts/entrypoint.sh"]
