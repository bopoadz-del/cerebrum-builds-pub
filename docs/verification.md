# Verification performed before hand-off

Run in this checkout, with the locked blocks present at `vendor/blocks/`
(paths pinned by `blocks.lock.json`) and a scratch `STORAGE_PATH`.

```sh
python -m pytest -q                       # 128 passed, 3 skipped
python scripts/factory_checks.py          # no findings; every capability fails closed
PLATFORM_TOKEN=dev-local-token \
TENANT_TOKENS='token-a:tenant-a,token-b:tenant-b' \
  python scripts/acceptance.py --self-check   # 23/23
env -i PATH="$PATH" HOME="$HOME" python -c "import app.main"   # imports with no environment
```

Live boot (uvicorn on a private high port, stopped by its captured PID):

```sh
STORAGE_PATH=/tmp/bootdata PLATFORM_TOKEN=boot-token \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8742
curl /health              # 200, checks process/disk/database/migrations, revision rev-n
curl /v1/capabilities     # 200, eight capabilities with fields and constraints
curl /v1/tracks           # 200, the two seed tracks validated at boot
```

The three skips are the Factory's own placeholders (`ENTITY = ''`) in the
lifecycle/deploy suites, filled when the Factory renders those files.

## The cross_tenant_404 token binding

`cross_tenant_404` posts as `Authorization: Bearer token-a` (literal) while
`CHECK_TENANT_TOKENS` holds `token-a-<random>:tenant-a,token-b-<random>:tenant-b`.
The token it sends is therefore only known to the service when the deployment
binds it. With the service started with those tokens —
`TENANT_TOKENS='token-a:tenant-a,token-b:tenant-b'` — the check passes:
`token-a` → `tenant-a`, `token-b` → `tenant-b`, cross-tenant read 404, and the
harness reports 23/23.

Run without that binding (the default self-check command above) the check
reports the honest 401 for an unconfigured token, 22/23. The product does not
accept a prefix or a derived token: anyone knowing `token-a` could then claim
`tenant-a`, which is the backdoor the `no_token_literal` floor exists to
prevent. The behaviour is also covered in-tree by:

* `tests/test_negative_floor.py` — tenant B's read of tenant A's record is 404;
* `tests/test_retrieval.py::test_the_corpus_is_tenant_scoped` — tenant B
  cannot retrieve tenant A's ingested document.

## What this pass repaired

The re-entry checkout carried `app/`, `docs/`, `scripts/` and `tests/` but
was missing the shipped top-level artefacts. They were restored and checked:
`track.v1.schema.json`, `tracks/coo.v1.yaml`, `tracks/ceo.v1.yaml`,
`alembic.ini`, `alembic/versions/0001_baseline.py` and `0002_lifecycle_audit.py`,
`Dockerfile`, `.env.example`, `.dockerignore`, `requirements.txt`,
`blocks.lock.json`, `vendor/blocks/`, `kits/platform/manifest.json`,
`deploy/contract.json`, `README.md`.

Two contract mismatches the refreshed suite exposed were fixed generally:

* `enrolment_and_calendar` treated an unparseable optional `start_date` /
  `timezone` as a whole-request refusal. Optional schedule inputs that cannot
  be parsed are now ignored with a `schedule_warnings` entry and the calendar
  falls back to today / UTC; `app.schedule.generate` itself still refuses a bad
  date and an unknown IANA zone (`tests/test_calendar.py`).
* `gradebook_and_transcript` refused the whole record when the optional
  `prior_average` was not numeric. Non-numeric enrichment is now ignored; the
  weighted average is unchanged.

## No programme content in product code

`tests/test_no_hardwiring.py` reads every seed under `tracks/` and searches
the shipped source (`app/**/*.py`, the console page, its JSON) for every
track name, audience, term title, week theme, reading title/source, case
title/prompt/outcome and rubric criterion label/description. It also refuses
a seed track id baked into Python source as a fallback. The check is derived
from the YAML, so a track the product has never seen is covered without
editing the test.

## One-record round-trip per capability

With `PLATFORM_TOKEN` set and a scratch `STORAGE_PATH`, each non-placeholder
capability was POSTed a payload built from its own `FIELDS`/`CONSTRAINTS`,
read back through `GET /v1/{capability_id}/{id}`, and found in
`GET /v1/{capability_id}`:

```
track_loader               post 200  get 200  listed
faculty_session            post 200  get 200  listed
memo_grading               post 200  get 200  listed
gradebook_and_transcript   post 200  get 200  listed
track_admin                post 200  get 200  listed
reading_and_case_library   post 200  get 200  listed
enrolment_and_calendar     503 placeholder (email_delivery) -- not judged
defense_and_capstone       503 placeholder (email_delivery) -- not judged
```

## Not measured here

* `docker_health_200` — no Docker daemon on this machine. The Dockerfile is
  runtime-only (`pip install -c constraints.txt -r requirements.txt`), declares
  `STORAGE_PATH=/data`, owns it as `appuser`, includes `vendor/`, `tracks/`,
  `alembic/` and `kits/`, and starts uvicorn through `scripts/entrypoint.sh`.
* `postgres_boot_200`, `audit_clean` — Store-gate measurements (`app/db.py`
  chooses the backend from `DATABASE_URL`; `app/store.py` has no connection of
  its own).
