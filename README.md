# Harbourline Civil Works — contracts administration

A contracts-administration platform for the Harbourline Civil Works project.
It governs progress claims, delay-damages exposure, QA/ITP records and the
project document register against the uploaded contract and BOQ as the single
source of record.

## Capabilities

| capability | what it does |
| --- | --- |
| `contract_source_of_record` | Pins Clause 8.2, 8.7, 11.1, 14.3 and 4.2 and the BOQ item/rate schedule from the uploaded documents. |
| `progress_claims` | Interim Payment Certificates from measured BOQ quantities, 5% retention, 50%/50% release at Taking-Over and Defects Notification Period end. |
| `delay_damages_tracking` | 730-day Time for Completion, projected taking-over, 0.1%/day damages capped at 10%, early warning at 90% of the cap. |
| `qa_itp_records` | Inspection and Test Plan records against BOQ work items with hold/witness points, evidence and sign-off. |
| `document_register` | Incoming/outgoing documents with revision control, distribution and a tamper-evident audit chain. |
| `contract_compliance_gate` | Gates claims, notifications and taking-over submissions against the pinned clauses; passes, refuses or escalates. |

Each capability persists to its own table (the capability id) under the
tenant resolved from the bearer token.

## HTTP

- `POST /v1/{capability}` — create and remember a record
- `GET /v1/{capability}` — list the caller's records (`limit`, `offset`, `sort`, `order`)
- `GET /v1/{capability}/{id}` — one record (404 for another tenant's id)
- `PUT` / `DELETE /v1/{capability}/{id}`
- `GET /health`, `GET /`, `GET /v1/capabilities`, `/v1/jobs`, `/v1/gates`, `/v1/provenance`
- `GET /metrics`

All `/v1` routes require `Authorization: Bearer <PLATFORM_TOKEN>`.

## Run locally

```sh
pip install -c constraints.txt -r requirements.txt
export PLATFORM_TOKEN=dev-local-token
export STORAGE_PATH=./data
uvicorn app.main:app --reload
```

The FastAPI lifespan applies Alembic to head before serving. The operator
console is at `/` and is served from `app/static/index.html`.

## Build and run the image

```sh
docker build -t harbourline .
docker run --rm -p 8000:8000 -e PLATFORM_TOKEN=... -v harbourline-data:/data harbourline
```

The image declares `STORAGE_PATH=/data`, creates it owned by the service
user, and answers `/health` before traffic. It never runs the test suite.

## Settings the operator must supply

| setting | meaning |
| --- | --- |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. Required: no token means 401. |
| `TENANT_TOKENS` | Comma-separated `token:tenant` pairs for further tenants. |
| `APPROVED_PRINCIPALS` | Comma-separated principals accepted on an approval field. |
| `STORAGE_PATH` | The one persistence root (SQLite file lives here). |
| `BACKUP_DIR` | Where scheduled backups are written; defaults to `STORAGE_PATH/backups`. |
| `DATABASE_URL` | Postgres when set; otherwise SQLite under `STORAGE_PATH`. |
| `PLATFORM_COUNTRY` | Country code, read at the point of use. |
| `PLATFORM_CURRENCY` | ISO currency. When unset the platform reads the currency from the BOQ's own rate-column header. |
| `PLATFORM_TAX_RATE` | Tax rate for money paths that need one. With none set they refuse. |

## Persistence and tenancy

Schema lives in `alembic/versions/0001_baseline.py` (one `op.create_table` per
entity, `tenant_id` on every table). `app/store.py` never creates a table and
routes every connection through `app.db`. SQLite runs in WAL, set once at
boot. A read is scoped to the authenticated tenant; another tenant's record
answers 404.

## Tests

```sh
pytest -q
pytest -m pilot -q
```

The factory suites (`tests/test_routes.py`, `tests/test_smoke.py`,
`tests/test_data_lifecycle.py`, `tests/test_deploy.py`,
`tests/test_domain_acceptance.py`) are the acceptance harness.
