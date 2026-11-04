# Harbourline Civil Works — Contracts Administration

A contracts-administration platform for the Harbourline Civil Works project.
The uploaded contract excerpt (`document:a2e79e3d662b42f1b56d5faafd651ffe_harbourline_contract.pdf`)
and BOQ (`document:402ecf72034f4692898b07cd2079bed2_harbourline_boq.xlsx`)
are the source of record. Every claim, deduction and record cites them.

## Capabilities

| Capability | What it does |
| --- | --- |
| `document_register` | Controlled register with revision, supersession, approval state and transmittal history. |
| `progress_claims` | Interim payment certificates measured against BOQ items P1–P5 / E1–E5 with Clause 14.3 retention. |
| `delay_damages_tracking` | Clause 8.2 time for completion, Clause 8.7 damages at 0.1%/day capped at 10%. |
| `qa_itp_records` | Inspection and test plan records, hold/witness points, outcomes and non-conformances. |
| `contract_clause_governance` | Indexes clauses 8.2, 8.7, 11.1, 14.3 and 4.2 as governed, auditable rules. |
| `payment_security_and_retention_ledger` | Clause 4.2 performance security and the Clause 14.3 retention release ledger. |
| `claims_analytics_dashboard` | Certified value vs BOQ, retention held, damages exposure, ITP close-out, register completeness. |

Each capability exposes `POST /v1/<capability>` (create), `GET /v1/<capability>`
(list), `GET /v1/<capability>/{id}` and `DELETE /v1/<capability>/{id}`, and answers with
`{ok, record, id, authority, blocks}`. The `authority` label states which layer
answered (1 certified > 2 documents > 3 formulas > 4 procedures).

Supporting surfaces: `GET /v1/capabilities`, `GET /v1/terms`,
`GET /v1/formulas`, `GET /v1/summary`, `POST /v1/rag/ingest`,
`POST|GET /v1/rag/query`, `GET /health`, `GET /metrics`. The console is served
at `/` and drives the capability routes, the contract terms, the formula
catalogue, retrieval and the portfolio summary.

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH=/tmp/harbourline-data
export PLATFORM_TOKEN=dev-local-token          # any value you choose
python -m alembic upgrade head                 # schema is versioned
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>, paste the token, press **Connect**.

### Docker

```sh
docker build -t harbourline .
docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN=change-me \
  -v harbourline-data:/data \
  harbourline
```

The image installs runtime requirements only (pinned by `constraints.txt`),
creates `/data` owned by the non-root service user, declares
`STORAGE_PATH=/data`, applies migrations on boot and only then serves. `/health`
answers 503 when the storage root, database or schema is not ready.

## Settings the operator must supply

None of these has a baked value; see `.env.example`.

| Setting | Meaning |
| --- | --- |
| `STORAGE_PATH` | Persistence root (SQLite `platform.db`, uploads, backups). |
| `DATABASE_URL` | Optional PostgreSQL DSN; absent means SQLite under `STORAGE_PATH`. |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. Required: no fallback. |
| `TENANT_TOKENS` | Extra tenants as comma-separated `token:tenant` pairs. |
| `APPROVED_PRINCIPALS` | Principals whose approval a governed record may name. |
| `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY` | Money locale. Read in order: this setting, then `docs/declared_locale.json`, then the currency the contract documents price in (`docs/source_of_record.json`). With none of the three, a money path refuses rather than assuming a currency. |
| `PLATFORM_TAX_RATE` | Tax rate for money paths; unset means the path refuses. |
| `PLATFORM_RATE_<NAME>` | Any named rate an operator owns (e.g. `PLATFORM_RATE_DELAY_DAMAGES`). |
| `BACKUP_DIR` | Backup destination; defaults under `STORAGE_PATH`. |
| `SENTRY_DSN` | Optional error reporting. |
| `PORT` | Listen port (default 8000). |

Contract values (730-day completion, 0.1%/day damages, 10% cap, 5% retention,
50/50 release, 10% performance security) are the customer's contract terms,
read from the governed clause records and changeable by them — never literals
in a calculation. The same holds for the currency: `docs/source_of_record.json`
records that the uploaded BOQ prices every line in SAR and the contract states
the Accepted Contract Amount in the same currency; it is data quoted from the
source of record, and `PLATFORM_CURRENCY` overrides it without a code change.

## Tests

```sh
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not pilot" -q     # code phase
python -m pytest -m pilot -q           # booted product, Store-backed blocks
python scripts/acceptance.py --self-check
```

`tests/` covers the capability contracts, routes, persistence/round-trips,
path safety, deploy/rollback behaviour and the data-lifecycle drill
(migrate up/down on populated data, backup → wipe → restore, parallel writes).

## Migrations and backups

- `alembic/versions/0001_baseline.py` creates one table per entity plus the
  work queue, idempotency and retrieval tables. `0002_lifecycle_audit.py` adds
  the lifecycle audit table. `python -m alembic upgrade head` is the only
  schema path; nothing calls `create_all()`.
- `scripts/backup.sh` archives the live database; `app/backup.py` performs
  backup, wipe and restore, and the drill in `tests/test_data_lifecycle.py`
  proves rows survive that round trip.
- `scripts/rollback.sh` restarts a prior image against the same disk.

## Known limitations

- Single instance, single disk: Render rollback restarts a process, it does not
  create HA. Losing the disk loses live SQLite and same-disk backups.
- The retrieval surface is empty until the customer supplies sources; the
  platform ships ingest/query, never seeded documents.
- `docs/blockers.md` records the one acceptance check that cannot pass in this
  environment, with the measurement that shows where the defect is.
