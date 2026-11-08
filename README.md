# Harbourline Civil Works Contracts Administration

A contracts-administration platform for the Harbourline Civil Works project.
The uploaded contract (`document:harbourline_contract.pdf`) and bill of
quantities (`document:harbourline_boq.xlsx`) are the source of record:

- **Contract and BOQ source of record** — the five contract clauses and ten
  BOQ line items, each traceable to its uploaded document.
- **Progress claims and payment certificates** — measured quantities, gross
  valuation, 5% retention per Clause 14.3 (50% released at Taking-Over, 50% at
  the end of the Defects Notification Period) and 10% performance security per
  Clause 4.2.
- **Delay-damages tracking** — days against the 730-day Time for Completion
  (Clause 8.2), damages at 0.1% of the Accepted Contract Amount per day capped
  at 10% (Clause 8.7), with the cap boundary reported.
- **QA/ITP records** — inspection lots tied to BOQ items, hold/witness points,
  test verdicts and sign-off; a passing test and a closed defect gate payment
  release.
- **Document register** — controlled revisions, status, checksum, search over
  the register and the text of attached documents, cited answers.
- **Claim review and dispute resolution** — a claim reviewed against the
  source of record, a determination with its basis and an evidence trail.

## Run

```sh
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt
export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export STORAGE_PATH="$PWD/data"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000/> for the console and paste the token. The schema
is applied by Alembic on boot (`0001_baseline` → `0002_lifecycle_audit`).
`GET /health` is fail-closed on process, persistent disk, database and
migration head; `GET /metrics` reports request count and latency.

### Container

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN="<operator token>" \
  -v harbourline-data:/app/data \
  harbourline-contracts
```

The image runs as a non-root user, declares `STORAGE_PATH=/app/data`, and its
healthcheck calls `/health` before traffic.

## Operator settings

Every value comes from the deploy environment; none is baked into the image.
The platform fails closed when a required one is absent.

| Setting | Purpose |
| --- | --- |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. Required: every `/v1` route answers 401 without a valid token. |
| `TENANT_TOKENS` | Comma-separated `token:tenant_id` pairs for additional tenants. |
| `APPROVED_PRINCIPALS` | Comma-separated principals allowed to sign an approval field. Free-text approvers are refused. |
| `STORAGE_PATH` | The one persistence root. The image sets `/app/data`. |
| `DATABASE_URL` | Optional Postgres URL; absent means SQLite at `$STORAGE_PATH/platform.db`. |
| `PORT` | HTTP port (default 8000). |
| `APP_REVISION`, `APP_MARK` | Process revision/mark used by the rollback drill. |
| `BACKUP_DIR` | Optional backup directory (default `$STORAGE_PATH/backups`). |

Money: the brief declares no country or currency, so no currency is chosen and
no tax rate is hardcoded. `app.money_settings` reports the label as
`WITHHELD (no currency declared)` until the operator declares one.

## API

One tenant-scoped family per capability:

```
POST   /v1/{capability}            create (validated against the model)
GET    /v1/{capability}            list the caller's records
GET    /v1/{capability}/{id}       read one (404 across tenants)
PUT    /v1/{capability}/{id}       update
DELETE /v1/{capability}/{id}       delete
GET    /v1/capabilities            declared fields and vocabularies
GET    /v1/ui                      the console's screen manifest
POST   /v1/document_register/intake   parse and register a file
GET    /v1/document_register/search   search the register and attached text
POST   /v1/document_register/ask      answer from the register with citations
```

The committed contract is `docs/openapi.json`.

## Authority and formulas

Answers carry their precedence layer: the source-of-record contract and BOQ
are layer 2 (documents); computed claim, delay and QA figures are layer 3
(formulas). Formula resolution order is the kernel first
(`universal:discount_amount_v1` for retention/performance security,
`universal:late_fee_simple_v1` for a per-day fee), then Store coverage (none
for this vertical), then an improvised formula labelled
`improvised, no Store coverage` — the capped delay-damages rule, sourced to
Clause 8.7 and recorded in `docs/provenance/provenance.json` and
`app/formulas/writer_definitions.jsonl`.

## Tests

```sh
python -m pytest -m "not pilot" -q   # code phase
python -m pytest -m pilot -q         # post-boot product phase
python scripts/factory_checks.py
python scripts/acceptance.py --self-check
```
