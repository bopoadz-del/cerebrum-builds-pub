# Delivery Service Platform

A delivery-service marketplace: the operator employs subcontractor drivers who
publish weekly availability and choose the suburbs they serve; customers browse
by suburb and slot and book them, with double-booking prevented and every
booking matched to a contractor whose service areas include that suburb.

## Run

```sh
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH=/var/lib/delivery
export PLATFORM_TOKEN=<random deploy token>
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The served console is at `/`, the API at `/v1`, health at `/health`, metrics at
`/metrics`, and OpenAPI at `/openapi.json` (committed copy: `docs/openapi.json`).

## Settings the operator supplies

| Setting | Meaning |
| --- | --- |
| `STORAGE_PATH` | Directory holding `platform.db` (the one persistence root). |
| `DATABASE_URL` | Optional Postgres URL; when absent SQLite under `STORAGE_PATH` is used. |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. Required; there is no default. |
| `TENANT_TOKENS` | Comma-separated `token:tenant` pairs for additional tenants. |
| `PLATFORM_COUNTRY` | Country for money paths. **Not declared by the customer — set before invoicing.** |
| `PLATFORM_CURRENCY` | Currency for money paths. **Not declared by the customer — set before invoicing.** |
| `PLATFORM_TAX_RATE` | Tax rate where a money path needs one. |
| `PLATFORM_RATE_PLATFORM_FEE` | Escrow fee rate the operator owns (for example `0.15`). |
| `PLATFORM_SLOT_MINUTES` | Minutes in one bookable slot (default `60`). |
| `PLATFORM_SERVICE_MINUTES` | Service window used when a booking gives no distinct end time (default `60`). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | SMTP delivery for the email and notification capabilities. |
| `SENDGRID_API_KEY` | SendGrid delivery when SMTP is not configured. |
| `EMAIL_PROVIDER` | `smtp`, `sendgrid` or `ses` when the provider must be explicit. |
| `NOTIFY_WEBHOOK_URL` | Operator webhook sink for notification delivery. |
| `BACKUP_DIR` | Backup destination (defaults to `STORAGE_PATH/backups`). |
| `SMS_GATEWAY_PROVIDER_..._CREDENTIALS` | Named placeholder: no SMS provider was specified. |
| `PAYMENT_PROCESSOR_..._CREDENTIALS` | Named placeholder: no payment processor was specified. |
| `ACCOUNTING_AND_TAX_VAT_SYSTEM_..._CREDENTIALS` | Named placeholder: no accounting/tax system was specified. |

Country, currency, tax and payout rules are open parameters. Money paths read
them from `app.money_settings` at run time and report `withheld` while unset.

## Capabilities

`customer_booking_flow`, `contractor_onboarding_and_service_areas`,
`contractor_availability_schedule`, `location_based_matching`,
`booking_status_lifecycle`, `booking_notifications`, `invoicing_and_payouts`,
`ops_back_office`, `audit`, `config`, `email`, `billing`.

Each has `POST /v1/<capability>`, `GET /v1/<capability>` and
`GET /v1/<capability>/<id>`. `GET /v1/customer_booking_flow/available`
returns the contractors whose active service areas include a suburb, whose
published schedule covers the requested slot, and whose open slots include it
(the same contractors and slots a booking request is validated against). `GET /v1/tenant` (and the
`X-Tenant-Id` response header) state the tenant the bearer token resolves to.

A live booking holds its slot from the moment it is requested: requested,
accepted and in-progress bookings all count against the contractor's declared
capacity, and an overlapping request beyond that capacity is refused (`409
error_kind: conflict`); only a completed or cancelled booking (stored
`closed`) releases it. A booking request may name a contractor that is not
yet onboarded only while it stays open -- any later lifecycle state requires
the contractor record, its active service area and its published schedule. `booking_status_lifecycle`
moves the referenced booking's status (`accepted` → `in_progress`,
`completed`/`cancelled` → `closed`).

### Managed suburb catalogue

The ops back office owns the tenant's suburb list. `GET
/v1/ops_back_office/suburbs` lists it together with the suburbs contractors
have proposed; `POST /v1/ops_back_office/suburbs` with
`{"suburb": "...", "region": "...", "active": true|false}` adds, renames or
retires one. The contractor owns the selection: a selected suburb is an
active service area unless the catalogue marks it inactive (retired). A
suburb the catalogue has not seen is still an active service area and is also
raised to ops as a proposal, so the catalogue follows the contractors rather
than gating them; only a retired suburb is withheld.

`booking_notifications` and `invoicing_and_payouts` answer HTTP 503
`error_kind: unavailable` naming the placeholder connector settings, and store
nothing.

## Audit

Every `POST /v1/audit` writes the block's immutable log entry and appends a
durable chain link to the tenant's audit row: `sequence`, `previous_digest`
and `chain_digest`. Verification re-walks the persisted rows, so the chain
survives a restart; there is no in-process ledger in the claim.

## Billing plans

The `plan` field is a declared vocabulary (`free`, `pro`, `enterprise`) and a
plan outside it is refused with HTTP 422. Limits are read from the billing
block's own `PLANS` table; the capability adds no price or quota of its own.

## Tests

```sh
python -m pytest -m "not pilot"     # code phase
python scripts/factory_checks.py    # writer behaviour probe
```
