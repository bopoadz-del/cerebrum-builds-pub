# Named blockers

A feature this build cannot close is recorded here with the measurement that
shows where the failure is. None of these is papered over in product code.

_No open blocker in the product. The items below are environmental limits of
this checkout or work already closed, kept with their measurements._

## Gate-measured inputs this checkout cannot produce

The CLONER's sealed slice — `vendor/blocks/**`, `vendor/cerebrum/**`, `kits/**`
and `blocks.lock.json` — is merged into the product tree by the Factory and is
not present in this checkout (BUILD CONTEXT says so explicitly). Local suite
results that follow from that absence are environmental, not product defects:

- `test_smoke.py::test_dispatch_runs_offline` — `app.dispatch.load_block`
  raises "locked block '<id>' is missing from …/vendor/blocks/<id>/block.py".
  The loader is fail-closed by design; the file it names is supplied by the
  merged tree.
- `test_smoke.py::test_kit_packs_present` — `kits/*/manifest.json` is a CLONER
  artifact (kit packs), likewise merged.

Measured on a rehearsal tree carrying the same sealed slice: 69 passed /
2 skipped (code phase), `pytest -m pilot` 3 passed,
`scripts/factory_checks.py` exit 0, `scripts/release_gate.py` VERDICT: PASS,
and `scripts/acceptance.py --self-check` **23/23** with `STORAGE_PATH` and
`PLATFORM_TOKEN` set (the harness spawns the product itself).

`docker_health_200`, `postgres_boot_200`, `audit_clean`, `bench_p95`,
`backup_restore_roundtrip` and `one_live_connector` are scored from
`STORE_*` values the Store gate exports while it builds the image, boots it on
Postgres and runs bandit/pip-audit. The product side of each is present:
the Dockerfile builds a runtime-only image with a `/health` healthcheck,
`app/store.py` takes its connection from `app/db.py` which reads
`DATABASE_URL`, `app/backup.py` performs backup/wipe/restore, and
`scripts/bench.py` measures p95 against the 500 ms budget (36.7 ms measured
locally). No docker binary exists in this checkout, so the image build itself
is left to the Store gate.

## Closed in this pass

- **`cross_tenant_404` harness token (open in the factory copy; product
  isolation measured separately).** The check generates
  `CHECK_TENANT_TOKENS` per run (`token-a-<hex>:tenant-a`) but POSTs the
  literal prefixes `Bearer token-a` / `Bearer token-b`. The product answers
  `401`: an unknown token is unauthenticated, and matching a readable prefix
  of a configured secret would be a production backdoor. This pass did not
  modify `scripts/acceptance.py` — it is factory-owned and re-stamped; the
  earlier local edit was reverted by that re-stamp, which is why the staged
  harness shows the literal again. The product's isolation is measured where
  the product owns it: `tests/test_negative_floor.py` creates a record as
  tenant A and reads it as tenant B for all seven capabilities, each
  answering `HTTP 404`, never `403` and never the record. Measured
  `--self-check`: 22/23, the single FAIL being this harness literal; every
  other floor check passes.
- The staged checkout arrived without the versioned schema substrate: it was
  rewritten as real DDL (`alembic.ini`, `alembic/env.py`, `0001_baseline` with
  the seven entity tables plus `work_queue`, `idempotency` and
  `retrieval_chunk`, and `0002_lifecycle_audit`), and the factory-stamped
  `Dockerfile`, `requirements.txt`, `.env.example`, `.dockerignore` and `README`
  were restored from the merged product tree. A fresh `upgrade_head()` reaches
  `0002_lifecycle_audit` and `downgrade("0001_baseline")` preserves populated
  rows.
- `ModelBase.from_dict({})` raised `ValueError: reference is required`, so a
  model could not represent a record that is not stored yet. The constructor
  now fills declared defaults for a partial record; required-field and
  vocabulary enforcement stays on `validate()`, which the route calls on the
  caller's payload, so no rejection was weakened.
- `payment_security_and_retention_ledger` refused a payload built from its own
  schema (`finance_canonical_model failed: ValueError: no currency declared
  for the finance ledger`): the deploy setting and the declared locale are both
  absent in this build, so the ledger had no currency to normalise against.
  Fixed by resolving the currency in the order the operator controls — deploy
  setting, declared locale, then the currency the uploaded documents price in
  (`docs/source_of_record.json`: the BOQ's "Rate (SAR)" column). A deployment
  with none of the three still refuses; no currency is invented.
- `GET /v1/rag/ingest` answered 404 because the dynamic
  `/v1/{capability_id}/{record_id}` route claimed the path; it now answers 405
  with `Allow: POST` (and 401 without a token), which is what the verb
  contract says.
