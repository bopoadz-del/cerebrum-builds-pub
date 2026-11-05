# Harbourline Civil Works — contracts administration

A contracts-administration platform for the Harbourline Civil Works project.
The uploaded contract excerpt and BOQ are the single source of record:

- `document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf`
- `document:9eef45a732d042dfb83157ec67068a75_harbourline_boq.xlsx`

Six capabilities:

| capability | what it does |
| --- | --- |
| `contract_source_of_record` | Holds contract clauses and BOQ items as the governing reference every other capability cites. |
| `progress_claims` | Interim Payment Certificates against the BOQ quantum: Clause 14.3 retention (5%, 50/50 release) and Clause 4.2 performance security (10%). |
| `time_and_delay_damages` | Clause 8.2 Time for Completion (730 days), Clause 8.7 delay damages (0.1%/day, 10% cap), Clause 11.1 Defects Notification Period (365 days). |
| `qa_itp_records` | Inspection and test records tied to the BOQ item they cover. |
| `document_register` | Controlled register of document revisions, status and provenance. |
| `role_based_access_and_audit` | Who may raise, review and certify, with an immutable decision trail. |

Every capability persists one tenant-scoped record through Alembic-managed
tables. A failed block call is refused (`ok: false`) and nothing is stored.

## Run it

The image installs runtime requirements only and needs no test suite.

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN="$(openssl rand -hex 24)" \
  -e TENANT_TOKENS="$(openssl rand -hex 24):tenant-b" \
  -v harbourline-data:/app/data \
  harbourline-contracts
```

`scripts/entrypoint.sh` runs `python -m alembic upgrade head` and then serves
uvicorn on `$PORT` (8000). A schema that cannot reach head refuses boot.
`/health` is 503 until process, persistent disk, database and migration head
all answer; it is the container healthcheck and the platform health check.

Without Docker:

```sh
python -m venv .venv && . .venv/bin/activate
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH="$PWD/data" PLATFORM_TOKEN=dev-local-token
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000/> for the operator console.

## Settings

Read from the environment only; nothing is baked into the image and there is
no fallback token. Unset `PLATFORM_TOKEN` means every `/v1` request answers
401. See `.env.example`.

| variable | required | meaning |
| --- | --- | --- |
| `PLATFORM_TOKEN` | yes | bearer token for the platform tenant |
| `TENANT_TOKENS` | no | `token:tenant_id` pairs, comma separated |
| `APPROVED_PRINCIPALS` | no | principals allowed to sign approval fields |
| `STORAGE_PATH` | no | the one persistence root (default `./data`; image `/app/data`) |
| `DATABASE_URL` | no | PostgreSQL DSN; unset means the SQLite file under `STORAGE_PATH` |
| `EMAIL_DELIVERY_CREDENTIALS` | no | only for the declared email placeholder |
| `FASTAPI_SYNC_THREADPOOL` | no | sync request threadpool (default 8) |

## HTTP surface

```text
GET  /health
GET  /metrics
GET  /
GET  /v1/capabilities
POST /v1/{capability_id}         create
GET  /v1/{capability_id}         list this tenant's records
GET  /v1/{capability_id}/{id}    read one (404 across tenants)
POST /v1/rag/ingest              {"text"|"content"|"paragraph": "..."}
GET|POST /v1/rag/query           {"q"|"query": "..."}
```

Authentication is `Authorization: Bearer <token>` on every `/v1` route. A
record owned by another tenant answers 404, never 403, so existence never
leaks. The committed OpenAPI document is `docs/openapi.json`.

## Data

One persistence root (`STORAGE_PATH`) and one engine decision (`app/db.py`).
Schema belongs to Alembic (`alembic/versions/0001_baseline.py` plus
`0002_lifecycle_audit.py`); the app runs no `create_all`.

- Backup: `scripts/backup.sh` (online SQLite backup into `$STORAGE_PATH/backups`).
- Rollback: `scripts/rollback.sh` restarts the previous image against the same
  disk. There is no replica; losing the disk loses the live database and
  same-disk backups. Rollback restores process identity, not a second copy.
- `tests/test_backup_restore.py` and `tests/test_data_lifecycle.py` exercise
  backup/restore, WAL, migration and concurrent writes.

## Blocks

The platform composes sealed Store blocks loaded from their locked paths
(`blocks.lock.json` -> `vendor/blocks/<id>/block.py`). A block absent from its
locked path fails start-up; there is no fallback copy under `app/`. Dispatch
passes the operation as the `action=` keyword and refuses to report success
over a failed block.

## Checks

```sh
python -m pytest -m "not pilot"      # code phase
python scripts/factory_checks.py     # writer gate probe
python scripts/acceptance.py --self-check
```

`scripts/acceptance.py` runs the Store gate's own checks; inputs only the gate
can measure (Docker, Postgres, the security scan) report SKIP locally.
