# Harbourline Civil Works — contracts administration

A contracts-administration platform for the Harbourline Civil Works project.
It treats the uploaded contract excerpt and BOQ as the source of record and
administers:

| Capability | What it does | Contract / BOQ source |
| --- | --- | --- |
| `progress_claims` | Interim Payment Certificates against the BOQ lines, 5% retention per certificate, released 50/50 | Clause 14.3; BOQ Preliminaries P1–P5 and Earthworks E1–E5 |
| `delay_damages_tracking` | Time for Completion, delay damages at 0.1%/day, capped at 10% of the Accepted Contract Amount, cap-day flag | Clauses 8.2, 8.7 |
| `qa_itp_records` | Inspection lots, hold points, witness points and test results per BOQ section | BOQ Preliminaries + Earthworks |
| `document_register` | Controlled register of contract, BOQ, drawings, reports and certificates with revision, checksum and provenance | The two uploaded documents |
| `performance_security_tracking` | Performance security at 10% of the Accepted Contract Amount, issue and expiry tracking | Clause 4.2 |
| `defects_notification_period` | 365-day Defects Notification Period, defect log and close-out evidence, second 50% retention release | Clause 11.1 |
| `claim_evidence_and_approvals` | Evidence classification and verification, approval routing, segregation of duties | Clauses 14.3 and the claims procedure |

Source documents (cited, never invented):

- `document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf`
- `document:a903d4ccba764b6f84b39e65b8b6add3_harbourline_boq.xlsx`

## Run it

```sh
cp .env.example .env          # then fill in the settings below
pip install -c constraints.txt -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000/>. The console discovers capabilities from
`GET /v1/capabilities`, prepares or certifies records against the live
`POST /v1/{capability}` and `GET /v1/{capability}` routes, and shows the
authority label of every answer.

Container:

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 --env-file .env -v harbourline-data:/app/data harbourline-contracts
```

The entrypoint runs `alembic upgrade head` against `STORAGE_PATH` and then
serves. `/health` answers 503 unless the process, the storage root, the
database and the migration head are all healthy.

## Settings the operator must set before use

Every value is read from the environment at run time; none is baked into
the image. See `.env.example` for the full list.

| Setting | Required | Meaning |
| --- | --- | --- |
| `PLATFORM_TOKEN` | yes | Bearer token for the platform tenant. With no token set, every `/v1` route answers 401. |
| `TENANT_TOKENS` | for extra tenants | `token:tenant` pairs, comma-separated. |
| `APPROVED_PRINCIPALS` | yes, to approve | Principals allowed to approve certificates. A free-text approver is refused. |
| `STORAGE_PATH` | yes | The single persistence root (SQLite file, backups). |
| `PLATFORM_CURRENCY` | yes | ISO currency of the BOQ and certificates. The uploaded BOQ is priced in SAR; set `PLATFORM_CURRENCY=SAR` unless the contract says otherwise. |
| `PLATFORM_COUNTRY` | yes | The country of the project. The contract excerpt does not state it — the operator declares it. |
| `PLATFORM_TAX_RATE` | when tax is applied | The tax rate the operator owns. No rate is assumed: while unset, a money path that needs it refuses. |
| `PLATFORM_RATE_RETENTION_PCT` | yes | Clause 14.3 retention percentage (contract: 5). |
| `PLATFORM_RATE_DELAY_DAMAGES_PCT_PER_DAY` | yes | Clause 8.7 daily percentage (contract: 0.1). |
| `PLATFORM_RATE_DELAY_DAMAGES_CAP_PCT` | yes | Clause 8.7 cap percentage (contract: 10). |
| `PLATFORM_RATE_PERFORMANCE_SECURITY_PCT` | yes | Clause 4.2 percentage (contract: 10). |
| `PLATFORM_RATE_TIME_FOR_COMPLETION_DAYS` | yes | Clause 8.2 Time for Completion in days (contract: 730). |
| `PLATFORM_RATE_DNP_DAYS` | yes | Clause 11.1 Defects Notification Period in days (contract: 365). |
| `PLATFORM_RATE_SECURITY_ALERT_DAYS` | no | Days before the security expiry at which an alert is raised (default 30). |
| `PROJECT_ACCOUNTING_LEDGER_CREDENTIALS` | for `progress_claims` | Declared placeholder connector. Until set, POST answers 503 `unavailable`. |
| `PRIMAVERA_P6_SCHEDULE_CREDENTIALS` | for `delay_damages_tracking` | Declared placeholder connector. |
| `PROJECT_EDMS_CREDENTIALS` | for `qa_itp_records` | Declared placeholder connector. |
| `BANK_GUARANTEE_AND_SURETY_PROVIDER_CREDENTIALS` | for `performance_security_tracking` | Declared placeholder connector. |
| `DEFECTS_AND_MAINTENANCE_SYSTEM_CREDENTIALS` | for `defects_notification_period` | Declared placeholder connector. |
| `DATABASE_URL` | no | Postgres URL. Absent means SQLite under `STORAGE_PATH`. |
| `BACKUP_DIR` | no | Where `scripts/backup.sh` writes. Defaults to `$STORAGE_PATH/backups`. |
| `SENTRY_DSN` | no | Error reporting, if the operator supplies one. |

The rates above are the customer's values from the uploaded excerpt; they
stay settings so the operator can change them without a redeploy.

## Layout

```
app/main.py              FastAPI app factory, /health, static console
app/routes.py            /v1 HTTP surface: auth, validation, handler, persist
app/actions/<cap>.py     one handler per capability (block composition)
app/models.py            capability FIELDS / CONSTRAINTS / ENTITY
app/store.py             tenant-scoped persistence over the alembic schema
app/db.py                the one place that decides SQLite vs Postgres
app/block_inputs.py      constructed block inputs + default block actions
app/dispatch.py          loads a locked Store block from vendor/blocks
app/formulas.py          the contract arithmetic (Clause 14.3 / 8.7 / 4.2)
app/authority.py         the four-layer precedence ladder
app/retrieval.py         tenant-scoped retrieval over registered documents
app/llm.py               offline extractive answers with authority labels
app/security.py          bearer auth, principal guards, SSRF guard
alembic/versions/        schema revisions (0001 baseline, 0002 audit)
app/static/index.html    the operator console
```

## Persistence

One storage root, `STORAGE_PATH`. Schema moves only through alembic
revisions: one `op.create_table` per capability entity, each carrying
`tenant_id`. `app/store.py` opens no database of its own — it takes its
connection from `app.db`, which is the single place that decides between
Postgres (`DATABASE_URL`) and SQLite. Every write on a route is
tenant-scoped from the authenticated principal, never from the payload.

## Placeholder connectors

Five capabilities call an integration the blueprint declares but this build
does not implement. Their POST answers HTTP 503 with `error_kind:
unavailable` and names the setting the operator must supply, before the
handler runs and before anything is stored. The handler is written for the
day the connector exists; the refusal is the honest answer until then.

## Tests

```sh
python -m pytest -m "not pilot" -q     # code phase: imports, routes, handlers
python -m pytest -q                    # full suite
python scripts/factory_checks.py       # writer behaviour probe
```

`tests/test_negative_floor.py` carries four counter-cases per capability: a
brief-invalid value refused, a cross-tenant read blocked, the stated rule
boundary exercised exactly on the line, and a fuzzed malformed payload.
