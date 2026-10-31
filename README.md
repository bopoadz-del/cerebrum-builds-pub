# Electric car manufacturing platform — pilot

Manager-only reasoning layer over **money** and **documents** for two Moroccan
EV plants (Casablanca and Tanger), each running five production lines on
12-hour shifts around the clock.

## What it does

- **Money.** Supplier costs, parts pricing and invoicing in MAD, with SAP ERP
  OData as the declared cost/invoice connector. Prices, markups and tax come
  from kernel formulas and `app.money_settings`.
- **Documents.** Managers upload BOMs, work instructions, quality procedures
  and supplier price lists (direct upload or OneDrive/Outlook). Retrieval is
  tenant-scoped and every answer carries its source citations and an authority
  label (documents = layer 2).
- **Alerts.** Threshold alerts on supplier cost / parts-price movements and
  nudges when a work instruction or quality procedure is revised. Delivery is
  MCP notification + Outlook email, with a dashboard entry.
- **Dashboard.** Open alerts, document revisions, cost records and widget
  layout for the manager console.

## Capabilities

| id | purpose | blocks |
| --- | --- | --- |
| `document_grounded_qa` | grounded answers with citations | vector_search, search, llm_enhancer |
| `supplier_cost_and_parts_pricing` | cost, pricing, invoices, SAP | finance_canonical_model, finance_import, finance_data_quality, finance_reconciliation, validation |
| `cost_price_movement_alerts` | threshold alerts | approval_rules, notification, email, analytics, dashboard |
| `document_revision_nudges` | revision nudges | version_diff, microsoft_365, notification, email, audit |
| `document_ingestion_from_m365_and_upload` | M365 + upload ingest | onedrive, microsoft_365, ingestion_provenance, pdf |
| `manager_dashboard` | manager console data | dashboard, analytics, aesthetic_kit |
| `manager_only_access` | manager sign-in and roles | auth, user_auth, multi_tenant_rbac |
| `sap_odata_connector` | SAP ERP OData surface | sap_odata_connector |

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH=./data
export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` and paste the token. The console discovers
capabilities from `GET /v1/capabilities` and drives the live routes.

Migrations run on boot (`app.migrations.upgrade_head`); the schema is alembic
`alembic/versions/0001_baseline.py`. The database is a single SQLite file under
`STORAGE_PATH`, or Postgres when `DATABASE_URL` is set.

Docker:

```sh
docker build -t plant-console .
docker run -p 8000:8000 -e PLATFORM_TOKEN=... -v plant-data:/data plant-console
```

## Settings the operator must supply

| setting | meaning |
| --- | --- |
| `PLATFORM_TOKEN` | bearer token for the manager tenant (required) |
| `TENANT_TOKENS` | optional `token:tenant` pairs for extra tenants |
| `STORAGE_PATH` | persistent data root (image default `/data`) |
| `DATABASE_URL` | optional Postgres URL; SQLite under `STORAGE_PATH` otherwise |
| `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY` | locale overrides; the declared locale is MA / MAD |
| `PLATFORM_TAX_RATE` | tax rate used by money paths; unset means the tax line is omitted |
| `PLATFORM_RATE_<NAME>` | any other named rate the operator owns |
| `SAP_ERP_CREDENTIALS` | SAP ERP OData credentials; without it `supplier_cost_and_parts_pricing` answers a typed 503 |
| `OUTLOOK_CREDENTIALS` | Outlook sender credentials; without it alert and ingestion capabilities answer a typed 503 |
| `ONEDRIVE_CLIENT_ID`, `ONEDRIVE_CLIENT_SECRET`, `ONEDRIVE_REFRESH_TOKEN` | optional OneDrive sync |
| `MICROSOFT365_CLIENT_ID`, `MICROSOFT365_CLIENT_SECRET` | optional Microsoft 365 Graph app registration |
| `BACKUP_DIR` | backup destination (default `STORAGE_PATH/backups`) |

No credential, token, country or rate is baked into the image.

## Retrieval contract

`POST /v1/rag/ingest` takes the document text in `text`, `content` or
`paragraph`. `GET|POST /v1/rag/query` answers from the tenant corpus with
citations. An empty corpus answers honestly; the platform never seeds
documents.

## Test

```sh
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not pilot"   # code-phase
python -m pytest -m pilot         # product gate
python scripts/acceptance.py --self-check
```
