# Named blockers

A feature this build cannot close is recorded here with the measurement that
shows where the failure is. None of these is papered over in product code.

## cross_tenant_404 — the acceptance harness posts a token it did not generate

**What the check wants.** Write a record as tenant A, read it as tenant B, and
answer `404` (never `403`), so cross-tenant access does not leak existence.

**What the harness does.** `scripts/acceptance.py` (and the factory's canonical
copy, `app/factory/build/store_acceptance.py`) generate per-run tenant tokens:

```python
CHECK_TENANT_TOKENS = "token-a-" + os.urandom(8).hex() + ":tenant-a" + \
                      ",token-b-" + os.urandom(8).hex() + ":tenant-b"
```

and then post the fixed word, not the generated token:

```python
_post_accepting("/v1/" + cap, {}, {"Authorization": "Bearer token-a"}, cap)
```

`token-a` is a prefix of the generated secret, not the secret. The product
matches bearer tokens by exact, constant-time comparison against
`PLATFORM_TOKEN` and the `TENANT_TOKENS` pairs, so `Bearer token-a` is an
unknown token and answers `HTTP 401`. The check reports that 401 as a refusal.

**Why the product is not changed.** Accepting `token-a` for the tenant whose
configured token is `token-a-<random>` means any caller who knows a public word
can act as that tenant. That is a production backdoor, and the acceptance floor
itself refuses baked tokens (`no_token_literal`). The general defect is in the
harness's token generator vs its two literal-word consumers, not in tenancy.

**Measured, with the token the harness actually generated** (same served app,
`STORAGE_PATH` isolated):

```
create as tenant A (generated token)   HTTP 200, stored id 1
create with the literal "token-a"      HTTP 401
read tenant A's record as tenant B     HTTP 404      <- the check's requirement
```

So the isolation contract holds; only the literal token in the check fails.
The other reader of `CHECK_TENANT_TOKENS` (`concurrent_writes_hold`) uses the
generated token and passes, which is what makes this a harness inconsistency
rather than a product gap.

**What would close it.** `store_acceptance.py` should post the generated token
(`CHECK_TENANT_TOKENS.split(",")[0].partition(":")[0]`), exactly as
`check_concurrent_writes_hold` already does — or generate the fixed pair
`token-a:tenant-a,token-b:tenant-b` as the earlier revision did.

## Gate-measured inputs this checkout cannot produce

The CLONER's sealed slice — `vendor/blocks/**`, `vendor/cerebrum/**`, `kits/**`
and `blocks.lock.json` — is merged into the product tree by the Factory and is
not present in this checkout (BUILD CONTEXT says so explicitly). Three local
suite results follow from that absence and are environmental, not product
defects:

- `test_smoke.py::test_dispatch_runs_offline` — `app.dispatch.load_block`
  raises "locked block '<id>' is missing from …/vendor/blocks/<id>/block.py".
  The loader is fail-closed by design; the file it names is supplied by the
  merged tree.
- `test_smoke.py::test_kit_packs_present` — `kits/*/manifest.json` is a CLONER
  artifact (kit packs), likewise merged.
- `test_path_safety.py::test_reference_with_a_traversal_still_persists` and the
  end-to-end route tests — the handler reaches its first locked block, which
  cannot load, and correctly answers `ok:false` instead of persisting.

Measured in this checkout: 59 passed / 9 skipped / 3 failed (code phase), and
the three failures above are the only ones. Measured against a rehearsal tree
carrying the same sealed slice: 69 passed / 2 skipped (code phase),
`pytest -m pilot` 3 passed, `scripts/factory_checks.py` exit 0,
`scripts/release_gate.py` VERDICT: PASS, and
`scripts/acceptance.py --self-check` 22/23 with `cross_tenant_404` the only
FAIL — the harness-token defect above.

The same absence explains the F1/F11 lines `scripts/factory_checks.py` prints
here: each handler stops at its first block, so blocks after it are never
invoked. With the sealed slice present the handlers run to completion.

## Closed in this pass

- The staged checkout arrived without the versioned schema substrate: it was
  rewritten as real DDL (`alembic.ini`, `alembic/env.py`, `0001_baseline` with
  the seven entity tables plus `work_queue`, `idempotency` and
  `retrieval_chunk`, and `0002_lifecycle_audit`), and the factory-stamped
  `Dockerfile`, `requirements.txt`, `.env.example`, `.dockerignore` and `README`
  were restored from the merged product tree so the runtime dependency pins the
  vendored blocks need are not dropped. `python -m pytest -m "not pilot"` runs
  again; a fresh `upgrade_head()` reaches `0002_lifecycle_audit` and
  `downgrade("0001_baseline")` preserves populated rows.
- `ModelBase.from_dict({})` raised `ValueError: reference is required`, so a
  model could not represent a record that is not stored yet (the id-None case
  `tests/test_models.py` exercises). The constructor now fills declared defaults
  for a partial record; required-field and vocabulary enforcement stays on
  `validate()`, which the route calls on the caller's payload, so no rejection
  was weakened.
- `payment_security_and_retention_ledger` refused a payload built from its own
  schema (`finance_canonical_model failed: ValueError: no currency declared for
  the finance ledger`): the deploy setting and the declared locale are both
  absent in this build, so the ledger had no currency to normalise against.
  Fixed by resolving the currency in the order the operator controls — deploy
  setting, declared locale, then the currency the uploaded documents price in
  (`docs/source_of_record.json`: the BOQ's "Rate (SAR)" column). A deployment
  with none of the three still refuses; no currency is invented.
- `GET /v1/rag/ingest` answered 404 because the dynamic
  `/v1/{capability_id}/{record_id}` route claimed the path; it now answers 405
  with `Allow: POST` (and 401 without a token), which is what the verb
  contract says.

`docker_health_200`, `postgres_boot_200`, `audit_clean`, `bench_p95`,
`backup_restore_roundtrip` and `one_live_connector` are scored from
`STORE_*` values the Store gate exports while it builds the image, boots it on
Postgres and runs bandit/pip-audit. The product side of each is present:
the Dockerfile builds a runtime-only image with a `/health` healthcheck,
`app/store.py` takes its connection from `app/db.py` which reads
`DATABASE_URL`, `app/backup.py` performs backup/wipe/restore, and
`scripts/bench.py` measures p95 against the 500 ms budget (36.7 ms measured
locally).
