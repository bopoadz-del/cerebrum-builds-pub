# Coffee-compost factory operations platform

A standalone, offline platform for the small Tunisian factory that turns
coffee waste into composting products. It serves 5–10 internal staff across
collection logistics, production, sales and finance:

| Capability | What it does | Bound Store blocks |
| --- | --- | --- |
| `collection_planning_tracking` | Plan, schedule and track coffee-waste pickups from cafés and other sources through delivery to the factory. | `task_listing`, `geolocation_tracking`, `workflow` |
| `batch_production_tracking` | Follow compost batches through mixing, active composting, curing, screening and quality checks. | `workflow`, `task_listing`, `audit` |
| `catalog_pricing_orders` | Manage the product catalog, price lists, customers and customer orders with line totals. | `vendor_catalog`, `workflow` |
| `invoicing_tunisian_vat` | Issue TND invoices with the customer’s Tunisian VAT rate, net/VAT/gross breakdown and payment state. | `billing`, `finance_canonical_model`, `finance_coa_governance` |
| `internal_staff_access` | Staff roster, roles (collection/logistics, production, sales, finance, manager, admin) and access state. | `auth`, `multi_tenant_rbac` |
| `operational_dashboard` | One live reading of collections, batches, orders, invoices and quality failures; the counts are measured from the tenant's own records, not typed in. | `dashboard`, `analytics` |

Every capability is a real, persisted record: the HTTP route saves it to its
Alembic-created table, tenant-scoped from the bearer token, and `GET` reads it
back. Every capability handler runs the blocks above through
`app.dispatch.execute` in-process; a block refusal is the capability’s refusal
and nothing is persisted.

## Quick start (local)

```sh
python -m venv .venv && . .venv/bin/activate
pip install -c constraints.txt -r requirements.txt -r requirements-dev.txt

export STORAGE_PATH=./data
export PLATFORM_TOKEN=dev-local-token
export PLATFORM_TAX_RATE=0.19
python -m alembic upgrade head          # or let the app lifespan do it
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>, paste the token, pick a capability, fill the
form and save. The console discovers the roster from `GET /v1/capabilities`,
posts records to the real capability routes, lists them back, and runs the
operations dashboard. Every answer shows its authority layer.

Health: `GET /health` (200 only when process, persistent disk, database and
Alembic head all hold; 503 otherwise). Metrics: `GET /metrics`.

## Quick start (Docker)

```sh
docker build -t coffee-compost:latest .
docker run --rm -p 8000:8000 \
  -e PLATFORM_TOKEN=change-me \
  -e PLATFORM_TAX_RATE=0.19 \
  -v coffee-data:/data \
  coffee-compost:latest
```

The entrypoint applies `alembic upgrade head` and then serves
`uvicorn app.main:app` on `$PORT` (default 8000). The image runs as a non-root
user; `/data` is created and owned by that user before the process starts.
`vendor/` and `kits/` must be present in the build context — they are part of
the product tree the Factory assembles.

## Configuration

Settings are read from the environment. There is **no baked token and no baked
tax rate**.

| Variable | Required | Meaning |
| --- | --- | --- |
| `PLATFORM_TOKEN` | yes | Bearer token for the platform tenant. No default: absent means 401. |
| `PLATFORM_TAX_RATE` | yes for VAT | Tunisian VAT rate as a decimal fraction (`0.19` = 19%). The customer owns it. |
| `STORAGE_PATH` | yes in a container | The single persistence root (`platform.db`, backups). Declared as `/data` in the image. |
| `DATABASE_URL` | no | Postgres instead of SQLite. One place decides: `app/db.py`. |
| `TENANT_TOKENS` | no | `token:tenant_id` pairs, comma separated, for additional tenants. |
| `TENANT_NAMES` | no | `tenant_id:Display name` pairs. |
| `APPROVED_PRINCIPALS` | no | Comma-separated principals allowed as `approved_by` on a staff revocation. |
| `PLATFORM_RATE_COMPOST_YIELD` | no | Finished compost kg per kg of input (default documented in `.env.example`). |
| `PICKUP_SHORTFALL_ALERT_PCT` | no | Collection shortfall alert threshold. |
| `COMPOST_*` | no | Curing target, moisture/pH/temperature/C:N quality bands. |
| `CATALOG_MIN_UNIT_PRICE`, `CATALOG_MAX_DISCOUNT_PCT` | no | Catalog guard rails. |
| `DASHBOARD_*` | no | Refresh seconds, unpaid-invoice alert threshold, theme. |
| `BACKUP_DIR` | no | Backup destination; defaults to `<STORAGE_PATH>/backups`. |
| `SENTRY_DSN` | no | Optional error reporting. Unset means no outbound reporting. |
| `APP_REVISION`, `APP_MARK` | no | Health/rollback identity (`rev-n`, `baseline` by default) — set at deploy so a rollback is a restart, not a schema wipe. |
| `BLOCKS_VENDOR_PATH` | no | Overrides the vendored block directory (default `vendor/blocks`). |
| `AUTH_FAILURE_MAX`, `AUTH_RATE_MAX`, `AUTH_RATE_WINDOW_S` | no | Failed-authentication throttle. |

`.env.example` lists every setting with an example value.

## HTTP surface

All `/v1` routes require `Authorization: Bearer <token>`; an unauthenticated
request is 401. Tenant identity comes only from the token — a payload that
names `tenant_id` or another reserved key is refused with 422.

For each capability `<cap>`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/v1/<cap>` | Validate (required fields, vocabulary, type, format, approver), run the capability and persist the record. |
| `GET` | `/v1/<cap>` | List the tenant’s records (`limit`, `offset`, `sort`, `order`, plus declared column filters). |
| `GET` | `/v1/<cap>/{id}` | Read one record; another tenant’s id is 404. |
| `PUT` | `/v1/<cap>/{id}` | Validate the payload, overlay it on the stored record (unnamed columns keep their stored value), re-check the approval the resulting record performs, run the capability, then update. |
| `DELETE` | `/v1/<cap>/{id}` | Delete the tenant’s record. |

Kernel/job routes: `GET /v1/jobs`, `/v1/catalog`, `/v1/inventory`,
`/v1/capabilities`, `/v1/gates`, `/v1/provenance`, `/v1/authority`.
`docs/openapi.json` is the committed route contract.

Enum fields refuse a value outside their declared vocabulary with 422;
`status` is exactly `open | in_progress | closed`. Numeric fields refuse the
non-standard JSON literals `NaN` / `Infinity` with 422 — they parse in Python
and compare false against every bound, so the type check is what stops them. Money fields are declared
`format: money`; weights/counts are `format: quantity`. Every answer carries
`authority` — the precedence.v1 layer (1 certified > 2 documents > 3 formulas
> 4 procedures) that produced it.

### Measured fields

A capability may declare some of its fields as a reading of the platform's own
records rather than a value the caller supplies. `operational_dashboard` does:
`collections_open`, `batches_in_curing`, `orders_open`, `invoices_unpaid` and
`quality_failures` are counted from the caller's tenant rows when the request
arrives, and `revenue_total` is the net-of-VAT value of the tenant's **paid**
invoices (`unit_price_ht x quantity`; VAT is not revenue). The rules live in
`app/models.py:AGGREGATES` and are applied in `app/routes.py` after the
caller's payload has been validated, through `app.store.count()` /
`app.store.total()` — tenant-scoped, bound parameters, declared columns only.
The posted number is still validated (the `>= 0` boundary and its 422 refusal
are on the payload), but the stored and returned reading is measured. That is
what makes the console's "Run operations dashboard" button answer with the
factory's current state instead of zeros.

## Persistence and operations

- The schema lives in Alembic revisions (`0001_baseline` for the six
  capability tables, `0002_lifecycle_audit`, `0003_work_queue`). There is no
  `create_all()`: `connect()` never creates a table.
- SQLite runs in WAL with a busy timeout; `upgrade_head()` switches WAL once at
  boot. `DATABASE_URL` selects Postgres and `app/db.py` is the only place that
  decides.
- Backups: `scripts/backup.sh` writes a timestamped copy under `BACKUP_DIR`;
  `app/backup.py` also supports retention pruning and restore
  (`create_backup`, `restore_backup`, `wipe_database`). Restore drills are in
  `tests/test_data_lifecycle.py`.
- The persisted work queue (`0003_work_queue`) supports enqueue/process through
  the kernel path (`app/domain_ops.py`). Idempotency keys replay the original
  record instead of writing a duplicate.

## Architecture

```
app/main.py          FastAPI app, lifespan (settings → migrations), /health, /
app/routes.py        the /v1 surface (kernel jobs + capability CRUD)
app/actions/         one handler per capability; each builds its own block inputs
                     and returns ok/record/authority; the route owns persistence
app/dispatch.py      loads vendor/blocks/<id>/block.py and executes it in-process
app/block_inputs.py  shapes a domain record into what each block accepts
app/block_contracts.py  harvested block contracts and declared default actions
app/store.py         tenant-scoped SQLite/Postgres persistence over app/db.py
app/models.py        the declared model (FIELDS + CONSTRAINTS) for each capability
app/formulas.py      kernel formulas by address (tax, gross/net, line totals) and
                     named process arithmetic (yield, mass loss, curing, shortfall)
app/authority.py     precedence.v1, as data
app/static/index.html  the single operator console
vendor/blocks/       the sealed block slice (read-only)
kits/                the kit pack manifests for the stocked blocks
```

The platform is offline: no block-store callback, no cloud LLM, no outbound
HTTP on a request path. `vendor/` is sealed — never edit it; domain work lives
in `app/` and `tests/`.

## Tests

```sh
python -m pytest -m "not pilot"     # code-phase gate: imports, routes, handlers
python -m pytest                     # full suite including Store-backed pilots
python scripts/factory_checks.py     # the writer behaviour probe (fail-closed etc.)
```

`tests/test_negative_floor.py` covers per-capability counter-cases: invalid
vocabulary, cross-tenant isolation, rule boundaries, and fuzzed payloads.

The Store gate's `cross_tenant_404` probe in the stamped
`scripts/acceptance.py` writes with the literal token `token-a` while the run
binds `token-a-<random>` through `TENANT_TOKENS`; the product refuses the
unbound token with 401 (as it must — accepting it would be a world-known
credential). `tests/test_negative_floor.py` proves the same property with the
bound token: a tenant B read of a tenant A record is HTTP 404. The probe is
Factory-owned and is not edited here.

## Limits of this build (prototype)

- Single-tenant by default; additional tenants are supported through
  `TENANT_TOKENS`, but there is no self-service tenant administration UI.
- The console is server-rendered/static (no build toolchain); it is served by
  FastAPI and uses only the platform’s own API.
- There is no outbound integration: cafés, customers and staff are recorded,
  not synchronised with external systems.
- No RAG/document corpus is shipped (this blueprint declares none).

## Code layout

| Path | What lives there |
| --- | --- |
| `app/main.py` | FastAPI app factory, lifespan (settings → migrations → preconditions), `/health`, `/metrics`, the console at `/`. |
| `app/routers/kernel.py` | The kernel roster routes (`/v1/jobs`, `/catalog`, `/inventory`, `/capabilities`, `/gates`, `/provenance`, `/authority`). |
| `app/routers/capabilities.py` | One CRUD router per capability: validate, run the handler, persist tenant-scoped, read back. |
| `app/routes.py` | Aggregates the two routers at `/v1` and publishes `ROUTE_ENTITIES`. |
| `app/actions/<capability>.py` | One handler per capability (`CAPABILITY_ID`, `handle(payload)`), declares `BLOCK_IDS` and calls every one. |
| `app/models.py` | `MODELS`: each capability's fields, constraints, entity, money/quantity declarations. |
| `app/dispatch.py`, `app/block_inputs.py` | In-process block dispatch and the per-block input contracts. |
| `app/formulas.py`, `app/money_settings.py` | Kernel formula addresses and the run-time money settings (no rate in code). |
| `app/store.py`, `alembic/versions/0001_baseline.py` | The declared schema and the tenant-scoped persistence over `app/db.py`. |
| `app/static/index.html`, `frontend/` | The one console; `frontend/build.py` renders it into `app/static/` during the image build. |

## Security posture

`docs/security_review.md` records the pass that was run against this tree: what
was attempted (unauthenticated calls, cross-tenant reads, reserved keys,
`NaN`/`Infinity`, free-text approvers, private-address URLs, concurrent writes)
and what held. Short version: every `/v1` route is authenticated and
tenant-scoped from the token alone, refusals are 4xx (never 500), no token or
rate is baked in, and the runtime makes no outbound call.
