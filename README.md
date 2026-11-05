# Harbourline Civil Works — contracts administration

A contracts-administration platform for the Harbourline Civil Works project.
The uploaded contract excerpt and BOQ are the single source of record; every
claim, delay assessment, inspection record and controlled document cites the
document it came from.

| Capability | What it does | Contract / BOQ source |
| --- | --- | --- |
| `contract_source_of_record` | Pins a clause or BOQ line to the uploaded document and cites `document:<filename>` | Contract excerpt; BOQ P1–P5 and E1–E5 |
| `progress_claims` | Interim Payment Certificates: BOQ valuation, 5% retention, performance security, 50/50 release points | Clauses 14.3, 4.2 |
| `time_and_delay_damages` | Time for Completion (730 days), delay damages 0.1%/day capped at 10% | Clauses 8.2, 8.7 |
| `qa_itp_records` | Inspection lots, hold and witness points, test result per BOQ item | BOQ Preliminaries + Earthworks |
| `document_register` | Controlled register with revision, checksum and provenance | Both uploaded documents |
| `role_based_access_and_audit` | Role/permission decisions in the fail-closed audit ledger | Contract administration roles |

Source documents:

- `document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf`
- `document:9eef45a732d042dfb83157ec67068a75_harbourline_boq.xlsx`

## Run it

```sh
cp .env.example .env          # then set PLATFORM_TOKEN
pip install -c constraints.txt -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000/>, paste the token into the console, and pick a
capability. Migrations run at start-up (`app.main` lifespan); the database file
lives at `$STORAGE_PATH/platform.db` and the service never creates schema at
connect time.

## API

```
POST /v1/{capability}        create a record (handler runs its bound blocks, route persists)
GET  /v1/{capability}        list this tenant's records
GET  /v1/{capability}/{id}   read one record (404 across tenants)
PUT  /v1/{capability}/{id}   update
DELETE /v1/{capability}/{id}
GET  /health                 fail-closed process/disk/database/migrations health
GET  /metrics                request count and latency
GET  /v1/jobs, /v1/catalog, /v1/inventory, /v1/capabilities, /v1/gates, /v1/provenance
```

## Docker

```sh
docker build -t harbourline-contracts .
docker run -p 8000:8000 -e PLATFORM_TOKEN=... -v harbourline-data:/app/data harbourline-contracts
```

The image declares `STORAGE_PATH=/app/data`, installs the local OCR engine, and
runs as a non-root user. The sealed `vendor/` block tree and `kits/` are copied
into the image unchanged; `blocks.lock.json` pins every block path.
