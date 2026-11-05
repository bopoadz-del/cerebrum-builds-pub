# Cerebrum Executive Programs

A data-driven executive-education platform for running 16-week programmes
(COO, CEO, or any other track) defined entirely in YAML track files.

Nothing programme-specific lives in product code: no track name, week theme,
book title, case name, company name or rubric text. Change the YAML and the
calendar, the faculty sessions, the reading library, the grading rubric and
the transcript change with it.

## What it does

| Capability | What an operator gets |
| --- | --- |
| `track_loader` | Every file under `tracks/` is validated at startup against `track.v1.schema.json`. An invalid file is refused with the offending field path (e.g. `rubric.weights`). |
| `enrolment_and_calendar` | Enrols a learner on a track with a start date and IANA timezone and generates the full calendar: 16 weeks x 6 fixed-template sessions (day offsets 0,1,2,4,5,6). Pins the track content version. |
| `faculty_session` | A chat session in one of six kernel modes (lecture, brief, socratic, sparring, oral_quiz, examiner). Content is built only from that week's record. Sparring refuses to write the learner's deliverable. Transcript stored, audit row per session. |
| `memo_grading` | A separate grader with no access to the faculty transcript scores a submission on the track's 5 x 20-point rubric through `formula_executor`, one verdict line per criterion, with provenance (kernel block, kernel version, rubric version, run id). Below the track's `rewrite_below` threshold the submission takes the rewrite path. |
| `gradebook_and_transcript` | Live weighted gradebook (weights from the track, 60/20/20 in the seeds) and a real PDF transcript containing every grade. |
| `defense_and_capstone` | Term defense on the term's last day, pass/fail, a re-sit within 7 days on failure, two reviewer invites, three capstone verdicts under the acceptance rule, and graduation only at the configured average with four passes and an accepted capstone. |
| `track_admin` | Upload or edit track YAML, validate it, see a week-level diff against the current version, pin a version per enrolment. |
| `reading_and_case_library` | Per-week readings and cases with their public sources; each case outcome stays withheld until that learner's `case_class` session opens it. |

Plus a tenant-scoped retrieval surface (`POST /v1/rag/ingest`,
`GET|POST /v1/rag/query`) that is empty until the customer supplies sources.

## Run it

```sh
pip install -c constraints.txt -r requirements.txt
export STORAGE_PATH=/data            # any writable directory
export PLATFORM_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
sh scripts/entrypoint.sh             # uvicorn on $PORT (default 8000)
```

The container image is the supported deployment:

```sh
docker build -t cerebrum-exec-programs .
docker run -p 8000:8000 -v exec-data:/data \
  -e PLATFORM_TOKEN=... cerebrum-exec-programs
```

Alembic migrations run in the application lifespan before traffic is served.
`STORAGE_PATH` is declared as an ENV in the Dockerfile and owned by the
runtime user; mount the volume there.

## Settings

Required before use:

| Setting | Meaning |
| --- | --- |
| `STORAGE_PATH` | One persistence root. The service refuses to start without it. |
| `PLATFORM_TOKEN` | Bearer token for the platform tenant. There is no baked default. |

Optional:

| Setting | Default | Meaning |
| --- | --- | --- |
| `TENANT_TOKENS` | unset | `token:tenant` pairs, comma-separated, for further tenants. |
| `TENANT_ROLES` | `Faculty` | `tenant:Role|Role` for those tenants. |
| `DATABASE_URL` | unset (SQLite under `STORAGE_PATH`) | PostgreSQL URL; read in one place (`app/db.py`). |
| `PLATFORM_SESSION_START` | `09:00` | Local start time of each session. |
| `PLATFORM_CRITERION_WORDS` | `60` | Words of evidence expected per rubric criterion. |
| `PLATFORM_GRADUATION_AVERAGE` | `80` | Average required for graduation. |
| `EMAIL_DELIVERY_CREDENTIALS` | unset | The declared placeholder connector below. |

Money: this brief names no country, currency or tax rate and the platform
takes no payments, so no currency or tax value is set anywhere. If fee
handling is added, `PLATFORM_CURRENCY`, `PLATFORM_COUNTRY` and
`PLATFORM_TAX_RATE` (see `app/money_settings.py`) become operator values with
no defaults.

## Declared placeholder connector

Email delivery is declared and **not built**: there is no relay credential in
the package. `enrolment_and_calendar` (week-1 reading email) and
`defense_and_capstone` (reviewer invites) answer HTTP 503 with
`error_kind: "unavailable"` naming `EMAIL_DELIVERY_CREDENTIALS`, and store
nothing. Their handlers, calendar generation, scheduling and PDF artefacts
are real; only the send is refused. Setting the variable does not enable
delivery in this build.

## Track files

`tracks/<id>.<version>.yaml`, validated against `track.v1.schema.json`
(JSON Schema draft 2020-12, `additionalProperties: false` everywhere). The
schema fixes the header (`schema_version`, `id`, `name`, `audience`,
`length_weeks` minimum 4, `hours_per_week`, `rubric`, `terms`), a rubric of
exactly five criteria at 20 points each with bands A/B/C/rewrite_below, and
weights that must sum to 100. The terms' weeks must run 1..`length_weeks`
without gaps; that cross-field rule is enforced in `app/track_schema.py`
because JSON Schema cannot state it.

Two seeds ship: `tracks/coo.v1.yaml` and `tracks/ceo.v1.yaml`.

The six-session weekly template (offsets 0,1,2,4,5,6 with 90/60/120/90/90/60
minutes) is a platform rule, not track content, and lives in
`app/schedule.py`.

## API

- `GET /health` — fail-closed readiness (process, disk, database, migrations)
- `GET /v1/capabilities` — capability discovery with fields and constraints
- `GET /v1/tracks` — validated track catalogue
- `GET /v1/formulas` — kernel definitions by address plus writer definitions
- `POST /v1/{capability}` / `GET /v1/{capability}` / `GET /v1/{capability}/{id}`
  / `PATCH` / `DELETE` — the capability surface, tenant scoped
- `POST /v1/rag/ingest`, `GET|POST /v1/rag/query` — the retrieval surface
- `GET /metrics`, `GET /v1/export` — observability and tenant export

Every `/v1` route answers 401 without a bearer token. A missing required field
is 422 naming the field; a value outside a declared vocabulary is 422 naming
the field and the accepted values. A record belonging to another tenant is
404, never 403 and never the record.

## Tests

```sh
python -m pytest -m "not pilot" -q      # code phase
python -m pytest -q                     # with the pilot suite (needs migrations)
python scripts/factory_checks.py        # the writer gate's own probe
```

## Layout

```
app/            application (actions/, routers/, store, dispatch, tracks, grading)
alembic/        schema revisions (one op.create_table per entity)
tracks/         programme content as YAML
kits/           the block pack this product composes
docs/           openapi.json, provenance, acceptance records
frontend/src/   the console component (the served UI is app/static/index.html)
```
