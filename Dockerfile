# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    STORAGE_PATH=/data

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .

# The console the image serves must be in the image, not only in the checkout.
RUN test -s app/static/index.html

RUN mkdir -p /data \
    && useradd --system --uid 10001 --home /app platform \
    && chown -R platform:platform /data /app

USER platform
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8000/health" || exit 1

# app.main's lifespan applies Alembic to head before traffic is accepted.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
