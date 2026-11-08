# Writer receipt — Harbourline Civil Works Contracts Administration

## Files authored in this pass

- `corpus/source_of_record.json` — contract clauses 4.2 / 8.2 / 8.7 / 11.1 /
  14.3 and BOQ items P1–P5 / E1–E5 with quantities and rates. `app.sources`
  and `app.contract_data` read every figure from it; no clause number or rate
  is typed into Python.
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` — the migration
  environment; the URL is resolved by `app.migrations` from `app.db`.
- `alembic/versions/0001_baseline.py` — one literal `op.create_table` per
  capability entity plus `work_queue` and `idempotency`, each carrying
  `tenant_id`.
- `alembic/versions/0002_lifecycle_audit.py` — the lifecycle audit table.
- `requirements.txt`, `requirements-dev.txt` — runtime and dev dependency
  declarations, installed against the Factory-owned `constraints.txt`.
- `Dockerfile` — one image: runtime requirements only, non-root `app` user,
  `STORAGE_PATH=/app/data` declared and owned by that user, healthcheck on
  `/health`, migrations on boot through the FastAPI lifespan.
- `.dockerignore`, `.env.example`, `deploy/contract.json`, `README.md` — the
  deploy contract, operator settings and run/rollback instructions.

## Verified

- Staging tree, `python -m pytest -m "not pilot" -q`: **39 passed, 2 failed**.
  The two failures are `tests/test_smoke.py::test_dispatch_runs_offline` and
  `::test_kit_packs_present`, which require the sealed `vendor/` and `kits/`
  packs absent from this staging checkout. Nothing was fabricated under those
  paths.
- Merged tree (this checkout over the sealed `vendor/` block implementations
  and a kit manifest), `python -m pytest -q`: **44 passed** — code and pilot
  phases, with all six capabilities executing their bound blocks. Three new
  counter-tests cover carried-forward quantity, a rejected determination that
  awards money, and distinct register revisions. The delay schedule now emits
  the block's dependency objects (`predecessor_id`/`type`/`lag`), not bare
  strings, so `cpm_engine` computes instead of refusing.
- Staging tree, `python -m pytest -m pilot -q`: **3 passed**.
- Six one-record POST/GET round-trips on a fresh `STORAGE_PATH`: every
  capability answered 200 with its own id and the record was listed back.
- `scripts/factory_checks.py`: probe clean (rc=0) in the merged tree — no
  `[halt]`, `[finding]` or `[miss]`. In the staging tree the probe reports
  only the two sealed-pack suite lines above.
- `scripts/acceptance.py --self-check`: **22/23**. `openapi_committed` (14
  paths), `ui_served_200`, `metrics_served`, `negative_floor`,
  `concurrent_writes_hold`, `migration_no_create_all`, `no_token_literal` and
  `authorship_floor` pass. Gate-only measurements (Docker health, Postgres
  boot, audit scan) report SKIP here.

## Post-review fixes landed

- **Backend**: one measured quantity now drives both the certificate and its
  carried-forward balance; a rejected/accepted/reduced determination must
  agree with its stated value; register revisions A/B no longer collapse to
  the same version; register audit identity is the authenticated principal.
- **Frontend**: a 401 or refused list no longer renders as "0 records"; Ask
  always calls the real route and tab text is labelled a preview; a failed
  create names its rejected field; the authority pill starts unlabelled.
- **Security**: authentication is a router dependency (before body parsing);
  uploads are bounded at 25 MiB and run on the threadpool; failed-auth
  attempts are rate limited; a block envelope carrying an error but no `ok`
  now fails closed; only missing-dependency errors are treated as
  unavailable.
- **DevOps**: image is `python:3.12-slim` (matching CI); `httpx` is declared
  for the shipped bench that CI runs with runtime requirements only; `pandas`
  and `pdfplumber` are declared for the bound `boq_processor`; nested caches
  are dockerignored; structured logging is reinstalled after Alembic's
  `fileConfig`; README installs the dev requirements for tests.

## Named blocker (harness, not product)

`cross_tenant_404` provisions `TENANT_TOKENS` with per-run random tokens
(`token-a-<random>:tenant-a,token-b-<random>:tenant-b`, scripts/acceptance.py
line ~183) but its requests post the literals `Bearer token-a` / `Bearer
token-b` (lines ~1559/1567). A correct product refuses those unprovisioned
tokens with 401. Accepting them would be the baked-token backdoor the floor
forbids, and `scripts/acceptance.py` is Factory-owned and must not be edited.
The same isolation is proven with the provisioned tokens: tenant-A create
200, tenant-B read 404.
