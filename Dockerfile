# Runtime only. Versions are pinned by constraints.txt (Factory-rendered).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    STORAGE_PATH=/data \
    BACKUP_DIR=/data/backups

WORKDIR /app

RUN useradd --create-home --uid 10001 platform \
    && mkdir -p /data \
    && chown -R platform:platform /data

COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .

RUN chown -R platform:platform /app

USER platform

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=4)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
