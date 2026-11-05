# Verification performed before hand-off

All commands were run from a merged tree: this checkout plus `vendor/` (the
locked blocks) and a generated `vendor/blocks/__init__.py` registry, which is
what the product image gets. `vendor/` is never written in this checkout.

```sh
python -m pytest -q                       # 94 passed, 4 skipped
python scripts/factory_checks.py          # no findings; every capability fails closed
python scripts/acceptance.py --self-check # 17 PASS, 6 SKIP, 1 FAIL (below)
```

The four skips are the Factory's own placeholders (`ENTITY = ''`) in the
lifecycle/deploy suites, which are filled when the Factory renders those files.

## The one failing acceptance check

`cross_tenant_404` posts as `Authorization: Bearer token-a` (literal) after
setting `TENANT_TOKENS` to `token-a-<random>:tenant-a,token-b-<random>:tenant-b`
— i.e. the token it sends is not a token it configured, so every capability
answers 401 and no record is created. The failure detail is exactly that:
`faculty_session: HTTP 401 ; gradebook_and_transcript: HTTP 401 ; ...`.

Accepting a prefix of a configured token would be a backdoor (anyone knowing
`token-a` could claim `tenant-a`), so the product does not do it. The
behaviour the check exists to measure is covered by:

* `tests/test_negative_floor.py` — tenant B's read of tenant A's record is 404;
* `tests/test_retrieval.py::test_the_corpus_is_tenant_scoped` — tenant B
  cannot retrieve tenant A's ingested document.

When the process is started with the tokens the harness presents (as the
Store gate's served container is), the check passes: `token-a` → `tenant-a`,
`token-b` → `tenant-b`, cross-tenant read 404.

## Not measured here

* `docker_health_200` — no Docker daemon on this machine; the Dockerfile is
  runtime-only (`pip install -c constraints.txt -r requirements.txt`), declares
  `STORAGE_PATH=/data`, owns it as the runtime user, and starts uvicorn
  through `scripts/entrypoint.sh`.
* `postgres_boot_200`, `audit_clean` — Store-gate measurements (`app/db.py`
  decides the backend; `app/store.py` has no connection of its own).
