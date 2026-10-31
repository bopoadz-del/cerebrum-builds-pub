FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_PATH=/data \
    PORT=8000

WORKDIR /app

COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 platform \
    && mkdir -p "$STORAGE_PATH" \
    && chown -R platform:platform "$STORAGE_PATH" /app \
    && chmod +x /app/scripts/entrypoint.sh 2>/dev/null || true

USER platform

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=4)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
