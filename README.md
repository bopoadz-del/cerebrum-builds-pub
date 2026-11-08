# Harbourline Contracts Administration

A contracts-administration platform for the Harbourline Civil Works project.
The uploaded contract and BOQ are the single source of record: every claim,
notice, inspection and register entry is tied back to a cited contract clause
or BOQ item (`document:<filename>`).

## What it serves

| Capability | What it does |
| --- | --- |
| `progress_claim_processing` | Prices measured BOQ quantities, assesses Interim Payment Certificates, takes retention at the Clause 14.3 rate, and routes the certificate through canonical finance and reconciliation blocks. |
| `delay_damages_tracking` | Runs the contract programme through the CPM engine and computes Clause 8.7 delay damages (0.1%/day, capped at 10%) with the kernel's late-fee identity. |
| `qa_itp_records` | Records ITP inspections, hold points and sign-offs, linked to a BOQ item and document, through the inspection workflow and audit chain. |
| `document_register` | Hashes, versions and clause-links controlled documents; diffs a revision against the one it supersedes. |
| `contract_clause_grounding` | Retrieves the exact clause or BOQ item, cites it, and refuses to invent an answer when the corpus holds no evidence. |
| `performance_security_tracking` | Tracks the Clause 4.2 Performance Security, its cover and its renewal window. |
| `compliance_dashboard` | One view of claims, delay exposure, ITP completion, register health and security validity, read from the tenant's own records. |

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export PLATFORM_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export STORAGE_PATH=/data
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The console is served at `/` (`app/static/index.html`). Paste the token, pick a
capability, submit a record, and ask the contract a question.

Migrations run on boot (`alembic upgrade head`). The database is SQLite under
`STORAGE_PATH` unless `DATABASE_URL` names Postgres; `app.db` is the one place
that decides.

### Docker

```sh
docker build -t harbourline-contracts .
docker run --rm -p 8000:8000 -e PLATFORM_TOKEN=... -v contracts-data:/data harbourline-contracts
```

`STORAGE_PATH` is declared as `/data` in the image; mount a volume there.

## Settings the operator must set

| Setting | Meaning |
| --- | --- |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. No default: without it every request is refused 401. |
| `TENANT_TOKENS` | Further principals, `token:tenant` pairs, comma separated. |
| `PLATFORM_TENANT` | Tenant id for `PLATFORM_TOKEN` (default `local`). |
| `STORAGE_PATH` | The one persistence root (database, register files, logs). |
| `DATABASE_URL` | Set to a Postgres DSN to run on Postgres; unset means SQLite. |
| `BACKUP_DIR` | Where `app.backup` writes archives (default `<STORAGE_PATH>/backups`). |
| `APPROVED_PRINCIPALS` | Comma-separated principals an approval field may name. A free-text approver is refused. |
| `PLATFORM_COUNTRY`, `PLATFORM_CURRENCY`, `PLATFORM_TAX_RATE`, `PLATFORM_RATE_<NAME>` | Money settings read by `app.money_settings` at the point of use. No currency was declared, so the BOQ's own label (SAR) is used for display; set `PLATFORM_CURRENCY` to override. |
| `SENTRY_DSN` | Optional error reporting. |

## Contract figures (all cited)

| Clause | Figure | Source |
| --- | --- | --- |
| 8.2 | Time for Completion 730 days | `document:3e1eb320b3a140acb0529606ee6d6431_harbourline_contract.pdf` |
| 8.7 | 0.1%/day, capped at 10% | same |
| 11.1 | Defects Notification Period 365 days | same |
| 14.3 | Retention 5% per certificate | same |
| 4.2 | Performance Security 10% | same |

The BOQ basis (P1–P5, E1–E5) and the Accepted Contract Amount are read from
`document:de42be780f4f4087b8d9520a040a4b78_harbourline_boq.xlsx`.

## Tests

```sh
python -m pytest -q              # code-phase suite
python scripts/factory_checks.py # the writer behaviour probe
PLATFORM_TOKEN=dev-local-token STORAGE_PATH=/tmp/acc python scripts/acceptance.py --self-check
```

`tests/test_harbourline_rules.py` carries the domain counter-cases: missing
required fields, out-of-vocabulary statuses, cross-tenant reads, the Clause
8.7 cap boundary, a fuzzed payload, and a retrieval negative control.

## Named blockers (not stubs)

These are Store/runtime gaps observed in the vendored tree, named here rather
than papered over:

- **`search`** is bound in the blueprint but its provider (`ddgs`) is not part
  of the offline runtime, so it is not declared on any capability; the document
  register uses `file_hasher`, `version_diff` and `audit_chain` instead.
- **`vector_search` similarity** needs scikit-learn, which the runtime does not
  ship; the block's offline fallback returns zero similarity. The block is
  still bound for index bookkeeping, and clause retrieval runs on the
  platform's own tenant-scoped lexical index (`app/retrieval.py`), which never
  invents a hit.
- **`knowledge`'s core vector store** (`vendor.cerebrum.core.vector_store`) is
  referenced but not vendored; `app.dispatch` aliases the module to the
  platform index so the block's `search` action runs against real chunks.
- **`document_engine`** loads its wrapper from a flat module path the vendored
  package layout does not expose; `app.dispatch` aliases the package module the
  block itself asks for. The block is not re-implemented.
- **LLM synthesis** is extractive and offline by design: answers quote the
  retrieved clause and cite its document; no provider key is required or used.
