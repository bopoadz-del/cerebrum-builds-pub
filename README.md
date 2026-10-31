# Electric-car manufacturing platform — pilot

A manager-only reasoning layer over **money** and **documents** for two
Moroccan EV plants (Casablanca and Tanger), each running five production
lines on 12-hour shifts around the clock.

## What it does

- **Money.** Supplier costs, parts pricing and invoices in MAD. Formula
  answers come from the universal kernel (markup on cost, tax on a net
  amount), the currency/country from the declared locale (MA / MAD), and
  SAP ERP costing/invoice data through the OData connector.
- **Documents.** Managers ask questions grounded in documents they ingest
  (BOMs, work instructions, quality procedures, supplier price lists) from
  OneDrive / Microsoft 365 or a direct upload. Retrieval is tenant-scoped
  and every answer carries its source citations and authority label
  (documents = layer 2).
- **Alerts.** Threshold alerts on supplier-cost and parts-price movements
  (absolute MAD movement against the manager's threshold), delivered as an
  MCP notification, an Outlook email and a dashboard entry.
- **Revision nudges.** When a work instruction or quality procedure is
  revised, affected managers get an Outlook email, a notification and a
  dashboard card, with the version diff and an audit entry.
- **Dashboard.** One console showing open alerts, cost/price movements in
  MAD, document revisions and the widget layout, plus a live Q&A panel.

## Capabilities and bound blocks

| id | purpose | blocks invoked |
| --- | --- | --- |
| `document_grounded_qa` | grounded answers with citations | vector_search, search, llm_enhancer |
| `supplier_cost_and_parts_pricing` | cost, pricing, invoices, formulas | finance_canonical_model, finance_import, finance_data_quality, finance_reconciliation, validation |
| `cost_price_movement_alerts` | threshold alerts | approval_rules, notification, email, analytics, dashboard |
| `document_revision_nudges` | revision nudges | version_diff, microsoft_365, notification, email, audit |
| `document_ingestion_from_m365_and_upload` | M365 + upload ingest, PDF text | onedrive, microsoft_365, ingestion_provenance, pdf |
| `manager_dashboard` | console data | dashboard, analytics, aesthetic_kit |
| `manager_only_access` | manager records and roles | auth, user_auth, multi_tenant_rbac |
| `sap_odata_connector` | SAP ERP OData surface | sap_odata_connector |

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH=./data
export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/`, paste the token. The console discovers the
capabilities from `GET /v1/capabilities` and drives the live POST/GET
routes. The same backend answers `GET /health` (fail-closed), `GET /metrics`
and `GET /v1/gates`.

Migrations run on boot (`app.migrations.upgrade_head`) and in the image
entrypoint. The schema lives in alembic revisions
(`alembic/versions/0001_baseline.py`, `0002_lifecycle_audit.py`); no
`create_all`. Storage is one SQLite file under `STORAGE_PATH`, or Postgres
when `DATABASE_URL` is set.

Docker:

```sh
docker build -t plant-console .
docker run -p 8000:8000 \
  -e PLATFORM_TOKEN=... \
  -e TENANT_TOKENS='token-a:tenant-a,token-b:tenant-b' \
  -v plant-data:/data plant-console
```

## Settings the operator must supply

| setting | meaning |
| --- | --- |
| `PLATFORM_TOKEN` | bearer token for the platform tenant (required) |
| `TENANT_TOKENS` | `token:tenant` pairs for further tenants, e.g. `token-a:tenant-a,token-b:tenant-b` |
| `STORAGE_PATH` | persistent data root (image default `/data`) |
| `DATABASE_URL` | optional Postgres URL; SQLite under `STORAGE_PATH` otherwise |
| `BACKUP_DIR` | backup destination (default `STORAGE_PATH/backups`) |
| `UPLOAD_ROOT` | directory a caller may point `file_path` at for PDF extraction (default `STORAGE_PATH/uploads`; paths outside it are refused) |
| `PLATFORM_TAX_RATE` | VAT/tax rate applied by money paths; unset means the tax line is omitted |
| `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY` | locale overrides; declared locale is MA / MAD |
| `PLATFORM_RATE_<NAME>` | any other named rate the operator owns |
| `SAP_ERP_CREDENTIALS` | SAP ERP OData credentials (named by the 503 refusal; the connector itself still has no adapter) |
| `OUTLOOK_CREDENTIALS` | Microsoft 365 Outlook credentials (named by the 503 refusal; the connector itself still has no adapter) |
| `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_REFRESH_TOKEN` | OneDrive sync |
| `MICROSOFT365_CLIENT_ID`, `MICROSOFT365_CLIENT_SECRET` | Microsoft 365 Graph app registration |
| `SENTRY_DSN` | optional error reporting |

No credential, token, country or tax rate is baked into the image.

## Retrieval contract

`POST /v1/rag/ingest` accepts the document text in `text`, `content` or
`paragraph`. `GET|POST /v1/rag/query` answers from the caller's tenant
corpus with citations and an authority label. An empty corpus answers
honestly; the platform never seeds documents.

`POST /v1/document_ingestion_from_m365_and_upload` records the source, the
plant and the document type, indexes the text for retrieval, and — when the
upload is a PDF — extracts the text through the pdf block. A text upload is
handed to the same parser as a one-page PDF so one extraction path and one
provenance record serve both.

## Test

```sh
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not pilot"   # code-phase suite
python -m pytest -m pilot         # product gate on the booted app
python scripts/factory_checks.py  # writer probe
python scripts/acceptance.py --self-check
```

## Known limits

- The two Outlook-backed capabilities and the SAP-backed pricing capability
  are declared placeholder connectors with no donor adapter in this image.
  They refuse every create with HTTP 503 `error_kind: unavailable`, naming
  the connector, and store nothing — setting the environment variable does
  not fabricate an adapter, an ERP row or a sent email. The money and
  document engines behind them (formulas, retrieval, PDF extraction) are
  exercised by the dashboard and the Q&A capability.
- `aesthetic_kit` ships disabled in the Store image (its kit manifest is not
  vendored), so `manager_dashboard` reports its verdict (`refused`) in the
  `aesthetic` field and uses the dashboard block's own layout.
- Retrieval is lexical (BM25-style scoring) over the tenant corpus; no
  embedding model is bundled, and the vector_search block indexes the
  documents the operator supplies.
- One process, one SQLite writer. Postgres is supported through
  `DATABASE_URL`; horizontal scaling is out of scope for the pilot.
