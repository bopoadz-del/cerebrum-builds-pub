# Cerebrum Executive Programs

A data-driven executive-education platform. Operators author 16-week executive
tracks as YAML validated against a shipped JSON Schema, enrol learners, and
version tracks; learners run a fixed weekly session template with AI faculty
chat in six kernel modes, submit memos graded independently against the rubric,
sit term defenses, defend a capstone to invited reviewers, and graduate on the
platform's own rule.

Platform tenant: `product`. Capabilities: `track_management`,
`enrolment_and_scheduling`, `ai_faculty_sessions`, `memo_grading`,
`gradebook_and_transcript`, `defenses_and_capstone`, `library_surfaces`,
`command_center_and_chat`.

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export PLATFORM_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export STORAGE_PATH="$PWD/data"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>, paste the token into the console, and pick a
capability. Migrations run at start-up (`app.main` lifespan); the database file
lives at `$STORAGE_PATH/platform.db` and the service never creates schema at
connect time.

Docker:

```sh
docker build -t cerebrum-executive .
docker run -p 8000:8000 -e PLATFORM_TOKEN=... -v cerebrum-data:/app/data cerebrum-executive
```

The image declares `STORAGE_PATH=/app/data` and creates it owned by the service
user before switching to it, so a fresh volume starts writable without root.

## Settings the operator supplies

| setting | why |
| --- | --- |
| `PLATFORM_TOKEN` | **required** — the platform tenant's bearer token. No default: without it every `/v1` route answers 401. |
| `TENANT_TOKENS` | optional, `token:tenant_id` pairs for further tenants. The tenant is always resolved from the token, never from a payload. |
| `STORAGE_PATH` | the one persistence root (declared as an image `ENV`). |
| `DATABASE_URL` | optional Postgres URL (`postgresql+psycopg://...`). `app/db.py` is the single place that decides; the store never opens a database of its own. |
| `APPROVED_PRINCIPALS` | comma-separated principals allowed to sign an approval field. A free-text approver is refused. |
| `EMAIL_DELIVERY_CREDENTIALS` | required by the email-delivery connector. Until the transport exists, `enrolment_and_scheduling` and `defenses_and_capstone` answer the typed HTTP 503 `error_kind: unavailable`. |
| `PLATFORM_MASTERY_FLOOR` | graduation / gradebook floor (default 80, the brief's value). |
| `PLATFORM_MEMO_PASS_FLOOR`, `PLATFORM_MEMO_MERIT_FLOOR`, `PLATFORM_MEMO_DISTINCTION_FLOOR` | memo bands (defaults 70 / 80 / 90, the brief's values). |
| `SENTRY_DSN` | optional; observability honours it when set. |

## Shape

```
app/main.py            ASGI app: lifespan migrations, /health, /metrics, console
app/routes.py          /v1 capability family + kernel surfaces (jobs, catalog, gates, provenance)
app/rag_routes.py      POST /v1/rag/ingest, GET|POST /v1/rag/query
app/actions/<cap>.py   one handler per capability (AUTHORED_BY stamped)
app/models.py          the declared contract: FIELDS, CONSTRAINTS, ENTITY
app/store.py           tenant-scoped persistence over app.db (Core statements, bound params)
app/db.py              the one backend decision (DATABASE_URL, else STORAGE_PATH/platform.db)
app/dispatch.py        locked block loader + the one execute() path
app/block_inputs.py    constructs block inputs; prepared event_bus workflow steps
app/tenancy.py         token -> tenant; app/security.py edge auth and refusal shapes
app/formulas/          formula definitions (kernel definitions first, then product ones)
app/llm.py             offline faculty (six modes) and the separate memo grader
app/retrieval.py       tenant-scoped ingest/query over the corpus the customer supplies
alembic/versions/      0001_baseline (one table per entity), 0002_lifecycle_audit
vendor/blocks/<id>/    the sealed Store blocks, pinned by blocks.lock.json
kits/platform/         the kit manifest this build was composed from
docs/track.v1.schema.json, docs/tracks/  the track schema and the seed COO/CEO tracks
```

The console is served from `app/static/index.html`; `frontend/src/App.tsx` is
the same console as source (see `frontend/README.md`).

## Tests

```sh
python -m pytest -m "not pilot" -q     # code phase: imports, routes, handlers
python -m pytest -m pilot -q           # post-boot: kernel S12 outcomes
python scripts/factory_checks.py       # the writer behaviour probe
python scripts/acceptance.py --self-check
```

## Authority

Every answer carries its layer: 1 certified > 2 documents > 3 formulas >
4 procedures, as versioned data (`app/cerebrum_product_kernel/precedence_ladder.v1.json`).
The platform tells the caller which layer won and what each losing layer would
have said; no model chooses.

## Known limitation in the acceptance harness

`scripts/acceptance.py::check_cross_tenant_404` writes as `Bearer token-a`,
a token its own run never binds (it generates `token-a-<hex>:tenant-a` in
`CHECK_TENANT_TOKENS`). Bound tokens are the only ones accepted, so that one
POST answers 401 and the check reports FAIL. Cross-tenant isolation itself is
implemented (another tenant's record answers 404, never 403) and is covered by
`tests/test_product_isolation.py`.
