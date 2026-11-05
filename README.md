# Harbourline Civil Works — Contracts Administration

A contracts-administration platform for the Harbourline Civil Works project.
It uses the uploaded contract excerpt and Bill of Quantities as the source of
record and serves four capabilities:

| Capability | What it does | Bound Store blocks |
| --- | --- | --- |
| `progress_claim_administration` | Prices an interim payment certificate against the BOQ, applies Clause 14.3 retention and Clause 4.2 performance security, reconciles claimed vs BOQ value, ingests the contract clauses as approval candidates | `boq_processor`, `finance_reconciliation`, `approval_rules` |
| `delay_damages_tracking` | Clause 8.7 position: 0.1%/day, capped at 10% of the Accepted Contract Amount, validated against the 730-day Clause 8.2 duration | `formula_executor`, `validation` |
| `qa_itp_records` | Inspection and test plan records linked to BOQ items and contract requirements, extracted and run through a prepared workflow | `document_engine`, `workflow` |
| `document_register` | Controlled document register with revision validation, search and SHA-256 checksum | `document_engine`, `search`, `version` |

Source of record (read at runtime, not copied into code):
`docs/source_of_record.json`, citing
`document:9624914db39345acbec7ff31dd838d91_harbourline_contract.pdf` and
`document:c5779cac9bcd4e2db8e33a44491360e5_harbourline_boq.xlsx`.

## Run locally

```sh
python -m venv .venv && . .venv/bin/activate
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH="$PWD/data"
export PLATFORM_TOKEN="$(python - <<'PY'
import secrets; print(secrets.token_urlsafe(32))
PY
)"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>, paste the token, and create a record. Alembic
runs at boot (`app.main` lifespan) before traffic is accepted.

## Settings the operator must supply

| Variable | Required | Meaning |
| --- | --- | --- |
| `PLATFORM_TOKEN` | yes | Bearer token for the platform tenant. There is **no** baked fallback; the product refuses every `/v1` route without it. |
| `TENANT_TOKENS` | no | Comma-separated `token:tenant` pairs for additional tenants. |
| `STORAGE_PATH` | yes in the image | The one persistence root. SQLite lives at `$STORAGE_PATH/platform.db`. The Dockerfile declares `/data`. |
| `DATABASE_URL` | no | When set, `app.db` selects Postgres and `app.store` takes its connection from there. When absent, SQLite under `STORAGE_PATH`. |
| `BACKUP_DIR` | no | Backup destination; defaults to `$STORAGE_PATH/backups`. |
| `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY`, `PLATFORM_TAX_RATE`, `PLATFORM_RATE_<NAME>` | no | Money settings. The BOQ declares SAR, so the platform uses SAR from the source of record; no currency or tax rate is hardcoded in `app/`. |
| `APPROVED_PRINCIPALS` | no | Comma-separated principals allowed to approve. A free-text approver is never trusted. |
| `SENTRY_DSN` | no | Honoured by the platform observability stack when present. |

No secret is baked into the image. `PLATFORM_TOKEN` is generated per deployment.

## Database and migrations

- `alembic/versions/0001_baseline.py` creates one table per capability, each
  with `tenant_id`, plus `work_queue` and `idempotency`.
- `app.migrations.upgrade_head()` runs on boot and switches SQLite to WAL once.
- `connect()` never creates schema; `create_all()` does not appear anywhere.
- Backups: `scripts/backup.sh` (creates and prunes). Restore is
  `app.backup.restore_backup(path)`.

## Docker

```sh
docker build -t harbourline .
docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN="$PLATFORM_TOKEN" \
  -v harbourline-data:/data \
  harbourline
```

The image installs runtime requirements against `constraints.txt`, runs as
UID 10001, owns `/data` before switching user, and answers `GET /health`
before accepting traffic. The healthcheck is fail-closed: process, writable
persistent disk, database and Alembic head must all pass.

## Tests

```sh
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not pilot" -q     # code phase
python -m pytest -m pilot -q          # against the booted product
python scripts/acceptance.py --self-check
python scripts/factory_checks.py
```

## UI

The console is served at `/` from `app/static/index.html`. It discovers the
capability roster from `GET /v1/capabilities`, drives every capability against
the real `/v1/{capability}` routes, lists persisted records, and prints the
authority label beside every answer. `frontend/src/App.tsx` mirrors the console
source; the built artifact is committed so the image serves it without a
Node build step.
