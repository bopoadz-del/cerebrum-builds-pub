# Harbourline Civil Works contracts platform — runtime image.
# Tests run in CI, not during the build.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    STORAGE_PATH=/data \
    PORT=8000

WORKDIR /srv

RUN groupadd --system appuser \
    && useradd --system --gid appuser --home /srv appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /srv

COPY constraints.txt requirements.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /srv

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,sys,urllib.request; \
url='http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health'; \
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
