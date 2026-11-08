# Harbourline Civil Works — contracts administration

A contracts office for one civil-works project. Interim payment certificates
are measured against the bill of quantities; delay exposure is computed from
the completion period and the damages clause; inspection lots, a
revision-controlled document register, the clause register and the commercial
position all draw on the same two uploaded documents. Every figure cites the
document and clause it came from.

The uploaded source of record is shipped as data in
`corpus/source_of_record.json` and cited as `document:harbourline_contract.pdf`
and `document:harbourline_boq.xlsx`.

## Capabilities

| Capability | What it does | Bound blocks |
| --- | --- | --- |
| `progress_claim_management` | Measures an IPC against a BOQ line, deducts retention and performance security at the contract's own percentages, opens a reconciliation run, registers the approval rule and audits the certification. | boq_processor, finance_reconciliation_workflow, approval_rules, audit |
| `delay_damages_tracking` | Counts elapsed days against the completion period, prices them at the contract's daily percentage up to its cap, and raises an event as exposure approaches that cap. | formula_executor, notification, audit |
| `qa_itp_records` | Captures inspection lots, hold and witness points, test verdicts, sign-offs and defect close-out, with evidence and audit chains. | document_engine, task_listing, evidence_chain, audit_chain |
| `document_register` | Revision history, checksums, review status and search for project documents, plus the intake, parse and cited-answer surface the console's chat screen uses. The external document-management connector answers a typed 503 until its credential is configured. | document_engine, version_diff, review, search |
| `contract_terms_governance` | Clause register for the five governing terms; compares a caller's value with the contract, reports divergence and passes the term through the governance gate and validation pipeline. | governance_gate, validation |
| `commercial_dashboard` | Claims by status, certified totals, retention held, delay exposure and outstanding inspection items, aggregated from the tenant's stored rows. | dashboard, analytics, portfolio_rollup |

## Console

`GET /` serves `app/static/index.html`. The page has three hash screens —
`#/operational_chat`, `#/command_center`, `#/resident_engineer` — and calls
only routes this product serves:

- `GET /v1/capabilities` — the declared roster and each capability's fields;
- `POST /v1/document_register/parse` — parse an attached PDF/XLSX/CSV/text and
  return its text (nothing stored);
- `POST /v1/document_register/intake` — file the parsed copy in the tenant's
  register;
- `POST /v1/document_register/ask` — a cited answer over the registered copies;
- `GET /v1/document_register/search?q=` — register search;
- `POST/GET /v1/{capability}` — create and list a capability's records.

The console holds no credential of its own: the operator pastes a deploy
token into the session panel. Until then the register routes answer 401, and
the chat screen says so; it can still preview an attachment read in the tab,
labelled as a preview.

## Run it

```sh
python -m venv .venv && . .venv/bin/activate
pip install -c constraints.txt -r requirements.txt
export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export STORAGE_PATH="$PWD/data"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Schema is migration-owned: boot runs `alembic upgrade head` through
`app.migrations` (and `scripts/entrypoint.sh` before serving), and
`app/store.py` never creates a table at connect time.

Docker:

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 -v harbourline-data:/app/data \
  -e PLATFORM_TOKEN="$PLATFORM_TOKEN" -e PLATFORM_CURRENCY=SAR \
  harbourline-contracts
```

The image declares `STORAGE_PATH=/app/data` and creates that directory owned by
the non-root user the service runs as. `vendor/` and `kits/` are copied into
the image by `COPY . .` and are not excluded by `.dockerignore`.

## Settings the operator must supply

| Setting | Purpose |
| --- | --- |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. Required; unset means every `/v1` route answers 401. |
| `TENANT_TOKENS` | Additional tenants as comma-separated `token:tenant_id` pairs. |
| `STORAGE_PATH` | The one persistence root (SQLite `platform.db` plus capability artifacts). |
| `PLATFORM_COUNTRY` | Country for money labels. |
| `PLATFORM_CURRENCY` | Currency for money labels. The uploaded BOQ states SAR. |
| `PLATFORM_TAX_RATE` | Tax rate for money paths that need one. |
| `APPROVED_PRINCIPALS` | Principals allowed to sign high-impact approval fields. |
| `PROJECT_DOCUMENT_MANAGEMENT_SYSTEM_E_G_PROCORE_ACONEX_CREDENTIALS` | Credential for the external document-management connector. Until set, `document_register` answers 503 `error_kind: unavailable` naming this setting. |

## Authority and formulas

Answers carry a precedence label: 1 certified > 2 documents > 3 formulas >
4 procedures (`app/cerebrum_product_kernel/precedence_ladder.v1.json`).
Contract terms cite layer 2. Retention, performance security, certified amount
and the daily delay-damages calculation are **improvised, no Store coverage**
definitions (the kernel's late-fee identity works from an annual rate, not
this contract's daily percentage with a hard cap); their source and label are
in `app/formulas/writer_definitions.jsonl`,
`app/formulas/new_domain_candidates.jsonl` and `docs/formula_provenance.json`,
and the label travels on the answer the console shows.

## Tests

```sh
python -m pytest -m "not pilot" -q
python -m pytest -m pilot -q
python scripts/factory_checks.py
python scripts/acceptance.py --self-check
```
