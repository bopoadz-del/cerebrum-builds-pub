# Harbourline Civil Works Contracts Administration Platform

A FastAPI service that administers a civil-works contract: it certifies interim
payment claims against the priced Bills of Quantities, tracks Time for Completion
and delay damages, records inspection and test plans, keeps a controlled document
register, schedules retention releases across the Defects Notification Period,
and refuses any claim, certificate or record it cannot ground in a governing
clause of the uploaded contract or a priced BOQ item.

Everything the platform asserts about the contract comes from two uploaded
documents - the contract excerpt (`docs/contract_terms.json`, source
`document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf`) and the
priced BOQ (`docs/boq_items.json`, source
`document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx`). No rate, cap
or period is written into the code: each is a declared contract term that an
operator can override from the environment (`app/contract.py`).

The work each capability performs is delegated to the locked Store blocks that
ship in `vendor/blocks/<id>/block.py` and are loaded by path through
`app/dispatch.py`. A block that is missing, or that answers a refusal, makes the
capability refuse - never a `200 ok` around a failed block.

## Capabilities

| Capability (`/v1/{capability}`) | What a record does | Contract basis it implements |
| --- | --- | --- |
| `progress_claims` | Certifies an Interim Payment Certificate: prices measured quantity against the BOQ item, holds retention, computes net payable, renders the certificate PDF and records the approval rule. | Clause **14.3** (retention held on each certificate) and Clause **4.2** (performance security), against the priced BOQ. |
| `delay_damages_tracking` | Assesses delay against Time for Completion and computes delay damages, uncapped and capped, with a CPM schedule and a validation pipeline. | Clause **8.2** (Time for Completion, 730 days) and Clause **8.7** (0.1% of the Accepted Contract Amount per day, capped at 10%). |
| `qa_itp_records` | Captures an inspection and test plan record against a priced BOQ work item: hold points that stop the works, and the named sign-off that releases them, chained as evidence and logged. | The BOQ work items (`docs/boq_items.json`); each record is chained as evidence (`evidence_chain`) and audited (`audit`). |
| `document_register` | Keeps a controlled register of the contract, BOQ, drawings and correspondence with revision, checksum and provenance. | Both uploaded documents, hashed and versioned (`document_engine`, `file_hasher`, `ingestion_provenance`, `version`). |
| `retention_defects_release` | Schedules the retention release across stages and holds the performance security obligation, with an approver and a state transition per release. | Clause **14.3** (5% retention, released 50% at Taking-Over and 50% at the end of the Defects Notification Period), Clause **11.1** (365-day Defects Notification Period) and Clause **4.2** (10% performance security). |
| `contract_verification_gate` | Verifies a claim, certificate or record only when it cites a governing clause or a priced BOQ item; anything ungrounded is flagged and evidence-free claims are refused. | The whole contract excerpt and the priced BOQ (`evidence_or_refuse`, `governance_gate`, `audit_chain`). |

`GET /v1/capabilities` returns this roster with each capability's fields, types,
required fields and allowed values; that response is the authoritative request
body schema for the capability endpoints.

## Run locally

```sh
pip install -c constraints.txt -r requirements.txt

# Apply the alembic head (idempotent; the app's lifespan applies it at boot too)
python -c "from app.migrations import upgrade_head; upgrade_head()"

export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export STORAGE_PATH="$PWD/data"
export PLATFORM_CURRENCY=SAR

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`constraints.txt` is the single pin table; `requirements.txt` declares the
runtime dependencies and repeats no version. `pytest` and `httpx` are pinned
there for test runs but are not installed into the runtime image.

With no `DATABASE_URL` the platform runs on a SQLite file at
`$STORAGE_PATH/platform.db`; set `DATABASE_URL` to a `postgresql://` URL to run
on Postgres instead (`app/db.py` decides, and `/health` reports which backend is
live).

## Build and run the image

```sh
docker build -t harbourline .

docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN="<your-token>" \
  -e PLATFORM_CURRENCY=SAR \
  -e APPROVED_PRINCIPALS="<approver-name>" \
  -v harbourline-data:/data \
  harbourline
```

- Base image `python:3.11-slim`, runs as the non-root user `appuser` (uid 10001).
- `vendor/`, `app/`, `alembic/` and `docs/` are all inside the image under
  `/app`; `.dockerignore` excludes only caches, `.git`, virtualenvs, `*.pyc`,
  `data/` and the operator's `.env`.
- The image applies the alembic head and then starts uvicorn
  (`CMD sh -c 'python -c "from app.migrations import upgrade_head; upgrade_head()" && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}'`).
  No tests and no release gate run at build time.
- `/data` is created owned by `appuser`, so mounting a volume there works
  without root. Mount one: without it, every restart starts from an empty
  database.
- `HEALTHCHECK` probes `http://127.0.0.1:${PORT}/health`; `/health` answers
  `503` until the storage path is writable, the database answers and alembic is
  at head, so an "unhealthy" container means exactly that.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `PLATFORM_TOKEN` | **Yes** | Bearer token of the platform principal. No default: unset means every request is refused (401). |
| `TENANT_TOKENS` | No | Comma-separated `token:tenant_id` pairs, one tenant per token. Unset means a single platform tenant. |
| `APPROVED_PRINCIPALS` | For approvals | Comma-separated principals allowed to approve a certification decision, a retention release or an ITP sign-off. A free-text approver is refused (403); unset means approval paths answer 503. |
| `PLATFORM_CURRENCY` | Yes, for money | ISO 4217 code the money paths report. |
| `PLATFORM_COUNTRY` | No | Country of the contract, when a money path asks for it. |
| `PLATFORM_TAX_RATE` | No | Tax rate as a fraction (`0.15`); a money path that needs it refuses when unset. |
| `STORAGE_PATH` | **Yes** | Writable root for the SQLite database, `work/` scratch files and backups. The image declares `/data`. |
| `BACKUP_DIR` | No | Where `app/backup.py` writes and reads backups. Defaults to `$STORAGE_PATH/backups`. |
| `DATABASE_URL` | No | `postgresql://` URL; when unset the platform uses the SQLite file under `STORAGE_PATH`. |
| `PLATFORM_TERM_RETENTION_RATE` | No | Clause 14.3 retention fraction (declared `0.05`). |
| `PLATFORM_TERM_RETENTION_RELEASE_FIRST_SHARE` | No | Clause 14.3 share released at Taking-Over (declared `0.5`). |
| `PLATFORM_TERM_PERFORMANCE_SECURITY_RATE` | No | Clause 4.2 performance security fraction (declared `0.1`). |
| `PLATFORM_TERM_DELAY_DAMAGES_DAILY_RATE` | No | Clause 8.7 damages per day of delay (declared `0.001`). |
| `PLATFORM_TERM_DELAY_DAMAGES_CAP_RATE` | No | Clause 8.7 cap on delay damages (declared `0.1`). |
| `PLATFORM_TERM_TIME_FOR_COMPLETION_DAYS` | No | Clause 8.2 Time for Completion in days (declared `730`). |
| `PLATFORM_TERM_DEFECTS_NOTIFICATION_DAYS` | No | Clause 11.1 Defects Notification Period in days (declared `365`). |
| `PORT` | No | Port uvicorn binds. The image declares `8000`. |
| `PLATFORM_TENANT` | No | Tenant id the platform token resolves to (default `platform`). |
| `PRODUCT_ROOT` | No | Root containing `vendor/` when it is not the code root; unset in the image. |

`PLATFORM_CURRENCY` and every contract rate above is an **operator setting, not
a value in the code**. The number shown in brackets is what the uploaded
contract excerpt declares (`docs/contract_terms.json`); the platform uses that
declared value when no override is set, and the override wins when one is. If a
customer's contract states a different retention, cap or period, set the
variable - do not edit the code. See `.env.example` for the annotated list.

## API surface

All routes take and return JSON. Authentication is checked before validation,
and the tenant is always taken from the authenticated principal, never from the
payload.

| Method and path | What it does |
| --- | --- |
| `POST /v1/{capability}` | Create a record for one capability. Body: the capability's own fields (see `GET /v1/capabilities`). An unknown field, a missing required field or a value outside an allowed set is refused with a `4xx` carrying `ok:false`, `error`, `rejected_field` and the `X-Rejected-Field` / `X-Rejection-Reason` headers. A refusal from the capability's own domain (an unknown BOQ item code, an approver nobody configured) is answered as data too - `ok:false` with the reason - never as a 500 and never as a record. |
| `GET /v1/{capability}` | List this tenant's records for that capability. |
| `GET /v1/{capability}/{id}` | Read one record (404 when it is not this tenant's). |
| `DELETE /v1/{capability}/{id}` | Delete one record (404 when it is not this tenant's). |
| `GET /v1/capabilities` | The capability roster: ids, titles, summaries, source documents, blocks, fields, required fields. |
| `GET /v1/jobs` | The kernel job roster and the route each kernel serves. |
| `GET /v1/catalog` | What the platform can do, per capability and block (COLLECTOR). |
| `GET /v1/inventory` | The locked blocks and the lock file the build pinned (CLONER). |
| `GET /v1/gates` | The acceptance checks the platform is scored against (TESTER). |
| `GET /v1/provenance` | The Store provenance record plus the record count per capability (STORE_MANAGER). |
| `GET /v1/meta` | Product name, live database backend and capability ids. |
| `GET /health` | Fail-closed process health: `200` only when the process serves, `STORAGE_PATH` is a writable directory, the configured database answers and alembic is at head; otherwise `503` with the failing check named. |
| `GET /metrics` | Prometheus text exposition (`text/plain; version=0.0.4`) for request counts and latencies. |
| `GET /` | The console, when a static bundle is present in `app/static`; otherwise a plain `503` saying it was not built into this image. |

The capability routes are `POST`, list, read and delete only. There is no update
endpoint: a corrected certificate is a new record, so the register keeps both.

## Authentication

Every route above requires a bearer token:

```sh
curl -s http://127.0.0.1:8000/v1/capabilities \
  -H "Authorization: Bearer $PLATFORM_TOKEN"
```

- `PLATFORM_TOKEN` authenticates the platform principal.
- `TENANT_TOKENS` (`token:tenant_id,token:tenant_id`) authenticates further
  tenants, one token each.
- A missing or unknown token is `401`; a record belonging to another tenant is
  `404`, not `403` - the platform never confirms that another tenant's record
  exists.
- Tokens are read from the environment on every request, so a rotated secret is
  picked up without a code change, and no token is ever echoed in a response.

## Backup and restore

`app/backup.py` is the backup path: a SQLite online backup of the live database,
a wipe, and a restore that puts the rows back and re-applies the alembic head.
Backups land in `$BACKUP_DIR` (default `$STORAGE_PATH/backups`).

```sh
# Take a backup (prints the file it wrote)
STORAGE_PATH=/data python -c "from app import backup; print(backup.create_backup())"

# List and prune, keeping the newest 7
STORAGE_PATH=/data python -c "from app import backup; print(*backup.list_backups(), sep='\n')"
STORAGE_PATH=/data python -c "from app import backup; print(backup.prune_backups(keep=7))"

# Destructive drill: wipe the live database, then restore the backup
STORAGE_PATH=/data python -c "from app import backup; backup.wipe_database()"
STORAGE_PATH=/data python -c "from app import backup; from pathlib import Path; print(backup.restore_backup(Path('/data/backups/platform-<stamp>.db')))"
```

A backup nobody has restored is a file, not a backup: the drill above is the
only thing that proves it. Restart the process (or let `/health` re-check) after
a restore. Stop the service first: `wipe_database()` removes the live file
underneath a running process.

## Limitations

These are real and deliberate; they are not roadmap items dressed as features.

- **No RAG corpus.** There is no retrieval index over the contract, the BOQ, the
  drawings or correspondence. Grounding is by clause reference and BOQ item code
  against the two uploaded documents in `docs/` (`app/contract.py`), which is
  exact and auditable but only covers what those documents contain. A clause
  that is not in the excerpt cannot be cited.
- **No LLM path.** Nothing in this service calls a model. Extraction, approval
  decisions, delay damages, retention releases and the verification gate are
  deterministic code over declared terms and priced items. There is no natural
  language parsing of correspondence and no model-generated text anywhere in a
  record.
- **`boq_processor` cannot parse a spreadsheet in this image.** The block parses
  spreadsheets through pandas, which is deliberately not a runtime dependency
  here (it is not in `requirements.txt`, so it is not in the image). The block
  therefore answers its readiness contract only, and the priced schedule the
  certificates and ITP records use is read from `docs/boq_items.json` - the
  uploaded BOQ, converted to JSON. Consequence: a BOQ supplied as a new `.xlsx`
  file is not priced by uploading it; it has to land in `docs/boq_items.json`.
- **Backups are SQLite-only.** `app/backup.py` writes a SQLite backup. On a
  Postgres deployment (`DATABASE_URL` set) `create_backup()` writes an empty
  file rather than a Postgres dump - use `pg_dump`/`pg_restore` there, and treat
  the retention/release records as the system of record for the workspace.
- **The console depends on a static bundle.** `app/main.py` serves `app/static`
  when it exists and answers `503` otherwise; the API is unaffected.
- **No update/PATCH endpoint and no pagination.** Listing a capability returns
  every record for the tenant, and corrections are new records.
