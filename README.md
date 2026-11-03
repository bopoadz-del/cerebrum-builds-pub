# Harbourline Civil Works — Contracts Administration

A contracts-administration platform for the Harbourline Civil Works
project. The uploaded contract excerpt and BOQ are the source of record
(`document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf`,
`document:a903d4ccba764b6f84b39e65b8b6add3_harbourline_boq.xlsx`).

Capabilities:

| id | what it does | connector |
| --- | --- | --- |
| `progress_claims` | IPCs against BOQ items, Clause 14.3 5% retention, 50/50 release | accounting ledger (declared placeholder → 503) |
| `delay_damages_tracking` | Clause 8.2 730 days, Clause 8.7 0.1%/day capped at 10% | Primavera P6 (declared placeholder → 503) |
| `qa_itp_records` | inspection lots, hold/witness points, test results | project EDMS (declared placeholder → 503) |
| `document_register` | controlled register, revision, provenance, checksum, retrieval | none — persists |
| `performance_security_tracking` | Clause 4.2 10% security and expiry alerts | bank/surety (declared placeholder → 503) |
| `defects_notification_period` | Clause 11.1 365-day DNP and retention release | defects system (declared placeholder → 503) |
| `claim_evidence_and_approvals` | evidence classification/verification, approval routing, segregation of duties | none — persists |

## Run

```sh
pip install -c constraints.txt -r requirements.txt
export PLATFORM_TOKEN=...            # required; no default
export STORAGE_PATH=/data            # required persistence root
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `/` for the console (enter the bearer token; it is held in the tab
only). Migrations run at boot; `/health` is fail-closed and `/metrics`
serves request counts and latency.

## Docker

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 -e PLATFORM_TOKEN=... -v contracts-data:/data harbourline-contracts
```

The image installs runtime requirements only (pinned by
`constraints.txt`), creates `/data` owned by the non-root service user,
and declares `STORAGE_PATH=/data`.

## Settings the operator MUST set

Every one is read from the environment; none is baked into the image.

- `PLATFORM_TOKEN` — platform tenant bearer token. Without it every `/v1`
  route answers 401 (fail closed).
- `TENANT_TOKENS` — further tenants as `token:tenant,token:tenant`.
- `STORAGE_PATH` — the single persistence root.
- `BACKUP_DIR` — where backups are written (default `STORAGE_PATH/backups`).
- `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY` — the brief declares no country or
  currency; until `PLATFORM_CURRENCY` is set, money answers `WITHHELD`.
- `PLATFORM_TAX_RATE` — any tax path refuses without it.
- `PLATFORM_RATE_RETENTION_PCT` (5), `PLATFORM_RATE_DELAY_DAMAGES_PCT_PER_DAY`
  (0.1), `PLATFORM_RATE_DELAY_DAMAGES_CAP_PCT` (10),
  `PLATFORM_RATE_TIME_FOR_COMPLETION_DAYS` (730), `PLATFORM_RATE_DNP_DAYS`
  (365), `PLATFORM_RATE_PERFORMANCE_SECURITY_PCT` (10),
  `PLATFORM_RATE_SECURITY_ALERT_DAYS` (30) — the contract figures, settable
  if the contract is amended.
- `PROJECT_ACCOUNTING_LEDGER_CREDENTIALS`, `PRIMAVERA_P6_SCHEDULE_CREDENTIALS`,
  `PROJECT_EDMS_CREDENTIALS`,
  `BANK_GUARANTEE_AND_SURETY_PROVIDER_CREDENTIALS`,
  `DEFECTS_AND_MAINTENANCE_SYSTEM_CREDENTIALS` — the five declared
  placeholder connectors. Until supplied those capabilities answer HTTP 503
  `error_kind=unavailable` naming the setting and store nothing.
- `APPROVED_PRINCIPALS` — comma-separated principal ids recognised as
  approvers.
- `DATABASE_URL` — optional Postgres; absent means SQLite under
  `STORAGE_PATH`.

## Design notes

- One tenant per request, resolved from the bearer token in `app/tenancy.py`;
  no route accepts a tenant from the payload. Another tenant's record reads
  as 404, never 403.
- Handlers return the domain decision and take `action=` as a keyword on
  every block call; the HTTP route is the only writer to the store, under
  the caller's tenant.
- Status is schema-enforced (`open | in_progress | closed`) and an unknown
  value is HTTP 422 naming the field and its allowed values.
- Blocks load only from their locked `vendor/blocks/<id>/block.py` path; a
  missing locked block is an error, never a fallback.
- `app/lib/pm_computations.py` supplies the CPM host computations the
  vendored `cpm_engine` declares it needs; circular networks fail loudly.

## Tests

```sh
python -m pytest -m "not pilot" -q
python -m pytest -m pilot -q         # booted product, Store-backed blocks
python scripts/factory_checks.py
python scripts/acceptance.py --self-check
```
