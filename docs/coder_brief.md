FACTORY CODING-AGENT BRIEF (one prompt — this is the product story)

You are manufacturing a full pilot repo, not a thin scaffold.

Exit condition — the run is DONE only when ALL of these are true:
- the PRODUCT gate passes (pytest -m pilot on the booted product)
- the STORE gate passes
- the ledger records pilot_ready=true
- the level grade is STORE_GREEN or FOUNDING_CUSTOMER_READY

Three gates (fail-closed; a gate that did not run is NOT a pass):
- CODE → CODE_GREEN: the code-phase suite (pytest -m "not pilot") — imports, routes, handlers
- PRODUCT → STORE_GREEN (with STORE): post-boot: the pilot-marked tests against the booted product, and a one-record round-trip per capability (POST creates, GET returns it)
- STORE → FOUNDING_CUSTOMER_READY when founding files + contracts hold: scripts/acceptance.py (≥12 measured checks) inside the Store-built Docker image — k/k required; restart-survival of the booted store; authorship floor is not acceptance

CODE_GREEN (code-cycle SUCCESS, pilot_ready=false) is a prototype, not Finished.
Do not treat templates-only output, stub handlers, skipped capabilities, or
pilot_ready=false as a finished product. Thin SUCCESS is a failure to finish.

Contracts you must honour on every capability you write:
- Blocks are action-dispatched. Pass action= as a keyword, never inside the
  payload dict. Prefer action=BLOCK_DEFAULT_ACTIONS.get(block_id).
- Call execute() for EVERY id in BLOCK_IDS. A declared block that is never
  invoked fails the WRITER behaviour gate and halts the build.
- Validate only the capability's own fields. Construct block inputs; do not
  demand block-specific keys (topic, sql/table, file paths, team_id,
  channel, steps) from the caller. The execute wrapper synthesizes those
  from the domain record. If you require a field, type, or vocabulary,
  declare it on the spec — the factory copies handler contracts onto the
  spec so the pilot suite can build a payload you will accept. Do not
  invent a second, stricter contract the spec cannot express.
- Offline platform: no network, no HTTP store callbacks, channel "mcp" only.
- WRITER gate writer_behaviour POSTs a payload built from each capability's own FIELDS + CONSTRAINTS (allowed_values[0], status=open, channel=email, generic str='sample'). Every handler must accept that payload. Declaring a stricter contract than the spec produces 'no capability accepted its own schema'.
- REUSE keep-path handlers must accept a schema-sample POST. Populate BLOCK_DEFAULT_ACTIONS from block.json / the factory Store map (including formula_executor, vector_search, capture, spec_analyzer, storage, and estate_registry) and pass action= as a keyword (action=BLOCK_DEFAULT_ACTIONS.get(block_id)). execute() with action=None is 'Unknown action: None'. Workflow step_0 without step.action is workflow: step_0 (event_bus): error. Store workflow reads input['result'] — a schema-sample POST that omits it fails as "workflow: RuntimeError: 'result'". CLONER must not rewrite assignment targets: name['result'] = becoming a .get() call fails as 'SyntaxError: cannot assign to function call' (queue / formula_executor). fail-closed keep original must still rewrite reads or TESTER refuses appointment_scheduling rejected a payload built from its own schema: "workflow: RuntimeError: 'result'". That miss is reuse/accept miss: HALT before TESTER. Photographed roster: patient_records_management, appointment_scheduling, prescription_management, billing_and_invoicing, client_communication_portal.
- PRODUCT one-record round-trip POSTs a schema-sample payload then re-reads store.list_all(entity) and GET /v1/{capability_id}. A miss is 'did not remember a record they were given'. Every capability must persist that record to its alembic entity via store.save(ENTITY, payload) (factory-grounded persist). POST POST raised OperationalError: no such table: <entity> is a miss. WRITER isolates STORAGE_PATH; PRODUCT must too — a leftover ./data/platform.db already at 0001_baseline is not a pass. Keyword-fallback veterinary_care_core, audit, dashboard are persistable capabilities.
- PRODUCT test_every_capability_route_accepts_payload POSTs a schema-sample payload then runs bound blocks. A capability that binds workflow + event_bus (appointment_scheduling / appointment_booking / automated_reminders / reminders_notifications style) must prepare EACH event_bus step including Store step_0, step_1 and step_2+ (block=event_bus, action=publish, topic, payload dict, message, channel=mcp, tool=event_bus) — never forward the raw sample as 'input': payload. Unprepared steps fail as 'workflow: step_N (event_bus): error'. An event_bus-first child fails as 'workflow: step_0 (event_bus): error'. An unprepared first factory child also fails as 'workflow: step_1 (event_bus): error'. A prepared step_1 plus an unprepared step_2 still fails as 'workflow: step_2 (event_bus): error' (schema sample refused (event_bus workflow step)). The factory wrap is not keep/done. WRITER emits a factory-grounded prepared event_bus step — do not execute("workflow", payload) with the raw schema sample. Store workflow / kit shim reads input['result'] or out['result'] — a schema-sample POST that omits it fails as "workflow: RuntimeError: 'result'". prepare_block_input and the keep-path emit MUST attach result from the first prepared step. CLONER must not rewrite assignment targets: name['result'] = becoming a .get() call fails as 'SyntaxError: cannot assign to function call'. fail-closed keep original must still rewrite reads or TESTER refuses appointment_scheduling rejected a payload built from its own schema: "workflow: RuntimeError: 'result'". Exact shape: {"block": "event_bus", "action": "publish", "input": {"topic": "<str>", "payload": {}, "message": "<str>", "channel": "mcp", "tool": "event_bus"}}.

This brief is the horizon. The user message is the compiled whole-job brief
(TARGET / STEP 0 INVENTORY / DO / ACCEPTANCE) — not one handle(), one spec,
or one route. One FACTORY_CODE_CLI writer; three gated phases (backend →
frontend+RAG → integration) with STOP / checkpoint between them. Fail-closed:
phase N acceptance before phase N+1. Resume skips landed writer phases.
A stage wall may hard-stop you so the factory can inspect what was achieved;
that stop is not permission to ship a scaffold.

# C-BRIEF TEMPLATE
revision: 2026-09-04
owner_shape: aviation
fill: deterministic (registry + block.json + domain pack + intake blueprint)
llm_writes_brief: never

Changes to this file require a new dated revision AND the lettings golden
reproduced (same capability roster, same compiled-brief fingerprint).

==================================================
TARGET
==================================================

Booted hospitality platform: StayFlow Hospitality Platform.
StayFlow is an all-in-one hotel booking and property management platform for independent hotels, boutique inns, and small hotel groups. It unifies real-time reservation management, room inventory and rate control, dynamic pricing, guest reviews, and operational analytics, while keeping staff and guests informed with automated notifications and AI-assisted search and recommendations.

Who it is for: hospitality operators
Roles: operator, admin

Capabilities:
- booking_management [REUSE]: dual-registered  blocks=['workflow', 'database', 'validation', 'event_bus', 'queue', 'audit']
- property_management [REUSE]: dual-registered (unverified REUSE dropped (Store exact-id present=false): estate_registry, estate_maintenance)  blocks=['database', 'team', 'workflow', 'audit']
- dynamic_pricing [REUSE]: dual-registered (unverified REUSE dropped (Store exact-id present=false): readiness_engine)  blocks=['formula_executor', 'recommendation_template', 'analytics', 'database']
- review_management [REUSE]: dual-registered  blocks=['capture', 'knowledge', 'vector_search', 'analytics', 'notification']
- analytics_dashboard [REUSE]: dual-registered (unverified REUSE dropped (Store exact-id present=false): portfolio_rollup)  blocks=['dashboard', 'analytics', 'database']
- notification_system [REUSE]: dual-registered  blocks=['notification', 'event_bus', 'queue', 'workflow']
- search_recommendation [REUSE]: dual-registered  blocks=['vector_search', 'knowledge', 'recommendation_template', 'memory', 'analytics']


==================================================
CUT 1 — STEP 0 INVENTORY + STOP
==================================================

Coder: list what the Store already provides. REUSE by exact block id, verified present — flag missing, never assume.

Store registry (exact ids, verified): analytics, audit, capture, dashboard, database, document_engine, estate_maintenance, estate_registry, event_bus, evidence_verifier, file_hasher, formula_executor, knowledge, memory, notification, portfolio_rollup, queue, readiness_engine, recommendation_template, spec_analyzer, storage, team, validation, vector_search, workflow

REUSE (verified present):
- booking_management: REUSE ['workflow', 'database', 'validation', 'event_bus', 'queue', 'audit'] (verified present in Store registry; handler source factory-grounded event_bus workflow; emit app/actions/booking_management.py)
- property_management: REUSE ['database', 'team', 'workflow', 'audit'] (verified present in Store registry; handler source factory-grounded persist; emit app/actions/property_management.py)
- dynamic_pricing: REUSE ['formula_executor', 'recommendation_template', 'analytics', 'database'] (verified present in Store registry; handler source factory-grounded persist; emit app/actions/dynamic_pricing.py)
- review_management: REUSE ['capture', 'knowledge', 'vector_search', 'analytics', 'notification'] (verified present in Store registry; handler source factory-grounded persist; emit app/actions/review_management.py)
- analytics_dashboard: REUSE ['dashboard', 'analytics', 'database'] (verified present in Store registry; handler source factory-grounded persist; emit app/actions/analytics_dashboard.py)
- notification_system: REUSE ['notification', 'event_bus', 'queue', 'workflow'] (verified present in Store registry; handler source factory-grounded event_bus workflow; emit app/actions/notification_system.py)
- search_recommendation: REUSE ['vector_search', 'knowledge', 'recommendation_template', 'memory', 'analytics'] (verified present in Store registry; handler source factory-grounded persist; emit app/actions/search_recommendation.py)

GAPS (you author; do not invent a block id):
- (none)

WORK ITEMS (C-BRIEF hole-fill; GENERATE gaps plus REUSE that still need handlers):
- booking_management: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- property_management: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- dynamic_pricing: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- review_management: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- analytics_dashboard: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- notification_system: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty
- search_recommendation: REUSE hole-fill — bind persist / event_bus / BLOCK_DEFAULT_ACTIONS; do not skip because inventory_gaps is empty

MISSING claimed REUSE (runner HALTS here if any):
- (none)

CUT 1 is read-only. Stop after this inventory. Do not build yet.


==================================================
CUT 2 — RUNNER VALIDATE
==================================================

CUT 2 — runner validates ids against the registry (not the coder).
Claimed REUSE that is not present HALTS before WRITER build, not at CLONER.
Verified present: workflow, database, validation, event_bus, queue, audit, database, team, workflow, audit, formula_executor, recommendation_template, analytics, database, capture, knowledge, vector_search, analytics, notification, dashboard, analytics, database, notification, event_bus, queue, workflow, vector_search, knowledge, recommendation_template, memory, analytics
Missing:


==================================================
CUT 3 — BUILD (DO)
==================================================

C-BRIEF / FACTORY_CODE_CLI owns this workspace even when STEP 0 is 100% REUSE/COMPOSE (no GENERATE gaps). Bind and write real handlers for every capability — deepen REUSE/COMPOSE (persist, constructed block inputs, BLOCK_DEFAULT_ACTIONS, prepared event_bus steps). Do not leave deterministic templates. Do not skip the CLI because inventory_gaps is empty. Do not re-implement a verified Store block from scratch — bind the registry-verified ids.
Every verified REUSE row must emit a loadable app/actions/{capability_id}.py (factory persist / event_bus envelope — the registry-verified handler source). A REUSE claim without that source is a GAP or HALT — do not reach writer_behaviour with ModuleNotFoundError.
Invocation contracts: pass action= as a keyword, never inside the payload dict.
Prefer action=BLOCK_DEFAULT_ACTIONS.get(block_id).
REUSE keep-path emit MUST populate BLOCK_DEFAULT_ACTIONS — execute() with action=None is Unknown action: None.
Call execute() for EVERY id in BLOCK_IDS.
Call execute() from app.dispatch only. Do not import app.actions, app.routes, or app.main from a handler. The factory owns app/actions/__init__.py — do not rewrite it with 'from app.actions import <capability>' eager re-exports. That circular import (live VetCare pet_records_management) makes writer_behaviour halt as workspace does not import before route honesty.
If you assign a block, you feed it — construct block inputs; do not demand block-specific keys (topic, sql/table, file paths, team_id, channel, steps) from the caller.
Declare vocabularies on the spec (schema), not in prose.
Envelope status vocabulary (schema-enforced): open | in_progress | closed.

WRITER gate writer_behaviour (baseline, before PRODUCT):
The harness POSTs /v1/{capability_id} with a payload built from
that capability's own FIELDS + CONSTRAINTS. A route or handle()
that refuses that payload before execute() fails the gate with:
  no capability accepted its own schema
Accept means HTTP 200 and not ok:false before a block is reached.
If you need a field, type, or vocabulary, declare it on the spec
so the sample includes it (allowed_values[0], bounds, format).
Do not invent a second, stricter contract the spec cannot express.
Do not require block-specific keys (topic, sql/table, file paths,
team_id, channel, steps) from the caller — construct those inputs.

Sampling rules (must match writer_behaviour probe _value):
- CONSTRAINTS.allowed_values[0] when declared
- status / *_status → open (envelope open | in_progress | closed)
- channel / *_channel → email (never the word sample)
- datetime / *_at / *_datetime → 2026-09-03T10:00:00
- date / *_date → 2026-09-03
- time / *_time → 10:00:00
- email-shaped names → sample@example.com
- int/float → min if set else 1 (min=0 samples as 0 in the probe)
- bool → false
- otherwise the word sample

Every capability's model already carries this envelope; the gate
POSTs it plus samples for any extra FIELDS you declare:
{"reference": "sample", "status": "open"}

PRODUCT / writer_behaviour schema-sample accept (REUSE keep-path):
The harness POSTs /v1/{capability_id} with a payload built from
that capability's own FIELDS + CONSTRAINTS, then runs bound
blocks. A keep-path handler that calls execute() with no
action= keyword (or action=None) fails as 'Unknown action'
/ 'Unknown action: None'. Workflow children without
step.action fail as workflow: step_0 (event_bus): error
(schema sample refused (event_bus workflow step)). Store workflow / kit shim
reads input['result'] / out['result']; a schema-sample POST
that omits it fails as workflow: RuntimeError: 'result'.
prepare_block_input and keep-path emit MUST attach result from
the first prepared step so accept-payload can persist.
CLONER emit_result_key_access rewrites reads of name['result']
only — assignment targets must stay subscripts. Rewriting
name['result'] = into a .get() call fails as SyntaxError: cannot assign to function call
(live queue.py ~189 / formula_executor ~242).
fail-closed keep original must still rewrite reads — a whole-module keep of the
original Store workflow.py leaves envelope['result'] /
input['result'] as KeyError → workflow: RuntimeError: 'result'
(appointment_scheduling rejected a payload built from its own schema).

factory-grounded REUSE emit MUST populate BLOCK_DEFAULT_ACTIONS
from vendored block.json (workspace vendor/, then factory
vendor_blocks_mirror / CEREBRUM_BLOCKS_ROOT action default or
options[0]) or the factory-known Store map. formula_executor
(and formula_executor_v2) must harvest a keyword action.
vector_search must harvest a keyword action (Store operation
default search) even when registry block.json has no action
input. capture must harvest a keyword action (Store-green
extract, sess_d10dfc28) even when registry / live vendor
block.json has no action input. Pass action= as a keyword —
never inside the payload dict.
Prefer action=BLOCK_DEFAULT_ACTIONS.get(block_id).

Photographed VetCare Hub REUSE roster (<SESSION_ID> /
<SESSION_ID>):
- patient_records_management
- appointment_scheduling
- prescription_management
- billing_and_invoicing
- client_communication_portal
Those ids are keep-path handlers, not per-cap micro-shots.
prescription_management / billing_and_invoicing bind
formula_executor — a missing default is reuse/accept miss.
patient_records_management binds vector_search — a missing
default is the <SESSION_ID> reuse/accept miss.
estate-operations maintenance_and_work_order_management /
security_and_access_logging bind capture — a missing default
is the <SESSION_ID> reuse/accept miss.
Steward property_onboarding binds spec_analyzer /
recommendation_template / readiness_engine — a missing
default is the <SESSION_ID> reuse/accept miss
(independent of the ~1490s phase wall).
Steward estate_registry binds storage — a missing default
is the <SESSION_ID> run3 reuse/accept miss
(tip 4120a07; independent of factory budget ramp).
A miss is reuse/accept miss: HALT before TESTER, do not burn
three PRODUCT reworks on Unknown action.

PRODUCT gate one-record round-trip (after WRITER, before STORE):
The harness boots the product (TestClient lifespan runs alembic)
on an isolated STORAGE_PATH, then POSTs /v1/{capability_id} with a
payload built from that capability's own FIELDS + CONSTRAINTS.
Accept means HTTP 200, not ok:false, store.list_all(entity) holds
the record, and GET /v1/{capability_id} returns it.
A miss is reported as: did not remember a record they were given
POST raising OperationalError: no such table: <entity> is that miss — the persist table was not migrated.

factory-grounded persist (not an LLM stub):
- every capability has an alembic 0001 table named spec.entity
  (capability_id with '-' → '_' when the spec omits entity)
- store.COLUMNS and store.save use that same entity
- handle() persists via store.save(ENTITY, payload) after blocks
  succeed (GENERATE with no blocks still persists)
- the route save(payload) writes the request, not handle()'s envelope
- do not persist to 'records' or a capability id that is not the entity
- do not rely on a leftover ./data/platform.db; PRODUCT isolates
  STORAGE_PATH the same way writer_behaviour does

Keyword-fallback architect rosters (live Veterinary Care Platform):
  veterinary_care_core, audit, dashboard
Those ids are persistable capabilities, not 'just blocks'. Each
must remember one record. Templated execute(block_id, payload)
or no_block_bound without store.save is not done.

GENERATE-gap factory-LLM fallthrough (after CLI billing/auth miss):
- write app/actions/{capability}.py through the same persist
  envelope as REUSE keep-path (_persist_record / store.save)
- alembic 0001 and store.COLUMNS still use spec.entity
- bind factory-LLM keys onto inventory GENERATE ids (exact,
  normalize, unique leftover) so vetcare_hub_veterinary_core
  is not dropped when the LLM writes veterinary_care_core
- empty / mismatched factory-LLM still emits the persist
  envelope — not a deterministic contract template and not a
  ≥2h CLI session. WRITER [check:round_trip] must not HALT
  solely because the billing keep-path omitted the handler

PRODUCT gate (after WRITER writer_behaviour) — accept-payload:
The harness runs tests/test_routes.py::test_every_capability_route_accepts_payload.
It POSTs /v1/{capability_id} with a payload built from that
capability's own FIELDS + CONSTRAINTS (same idea as
writer_behaviour; PRODUCT then executes the bound blocks).
A route that returns ok:false fails with:
  {capability} rejected a payload built from its own schema: workflow: step_N (event_bus): error
Named class: schema sample refused (event_bus workflow step); accept-payload persisted nothing; workflow: RuntimeError: 'result'.

These planned capabilities bind workflow and/or event_bus
(appointment / scheduling / booking / reminders style) and MUST
use the prepared step on EVERY event_bus child, including
automated_reminders Store step_0 (first child),
appointment_scheduling step_1 and appointment_booking step_2+:
- booking_management
- notification_system

PRODUCT schema-sample rules (roles_handlers._sample_payload):
- CONSTRAINTS.allowed_values[0] when declared
- status / *_status → open
- channel / *_channel → email (never the word sample)
- datetime / *_at / *_datetime → 2026-09-03T10:00:00
- date / *_date → 2026-09-03
- time / *_time → 10:00:00
- email-shaped names → guest@example.com
- otherwise the word sample

That schema sample is NOT an event_bus input. When a capability
binds workflow AND event_bus — or a reminders / appointment /
scheduling / booking-style id (appointment_scheduling /
appointment_booking) invents a workflow — do NOT set
ANY step input to payload. Store 0-indexes children: an
event_bus-first child fails PRODUCT as workflow: step_0 (event_bus): error
(automated_reminders class). An unprepared first factory
child also fails as workflow: step_1 (event_bus): error. step_1 prepared +
step_2 raw still fails as workflow: step_2 (event_bus): error.
The Store workflow records a child refusal as status=error — often
only the banner string, no inner message.
Store kit shims also read input['result'] / out['result'] and wrap
a missing key as workflow: RuntimeError: 'result'. The schema sample
does not include that key — prepare_block_input / keep-path emit
MUST attach result from the first prepared step so accept-payload
can persist. CLONER must not rewrite assignment targets:
name['result'] = becoming a .get() call fails as
SyntaxError: cannot assign to function call (queue.py ~189 /
formula_executor ~242).
fail-closed keep original must still rewrite reads — keeping
the whole Store workflow.py leaves envelope['result'] as
workflow: RuntimeError: 'result' (appointment_scheduling rejected a payload built from its own schema).
WRITER emits a factory-grounded prepared event_bus step for
appointment / booking / reminder capabilities — do not burn
rework on execute(block_id, payload) stubs, and do not
execute("workflow", payload) with the raw schema sample.
Construct each event_bus step (every child, including Store
step_0, step_1, and step_2+) in source. The factory execute wrap is a safety
net, not permission to keep/done an unprepared child:
- step['block'] = 'event_bus' (workflow reads block, not block_id)
- action=publish (BLOCK_DEFAULT_ACTIONS, keyword only)
- input.topic = non-empty str (event / event_type / event_name / reminder_type or a record summary)
- input.payload = dict of domain scalars (not the raw sample alone)
- input.message = non-empty str
- input.channel = 'mcp' (never 'sample'; 'email' without `to` is not notify-ready)
- input.tool = 'event_bus' (MCP notify requires block/tool; the schema sample has neither)
Exact prepared event_bus workflow step (copy this shape on
EVERY event_bus child — step_0, step_1, step_2, and later):
{
  "block": "event_bus",
  "action": "publish",
  "input": {
    "topic": "<non-empty str from event / reminder_type / record summary>",
    "payload": {"reference": "<domain scalar — not the raw schema sample>"},
    "message": "<non-empty str>",
    "channel": "mcp",
    "tool": "event_bus"
  }
}
Do not invent a second, unprepared event_bus child after a
prepared step. Do not invent a stricter workflow the spec
cannot express.

Launching-ready full-pilot authorship floor: emit ≥5 keepable agent-written app/actions/*.py handlers (or equivalent cli_authored_ids). Fewer than 5 is FACTORY_CODE_CLI_THIN_AUTHORSHIP — CODE_GREEN / pilot_ready=false, package 409. Do not treat the job as done below this floor.

Three tests per block are already owned by the harness (TESTER is not an LLM role).
Scope READS / WRITES / NEVER explicitly in each handler you author.
Budget wall: 1800s (FACTORY_CODER_BUDGET_S / staged wall).

# PHASE 1 of 3 — BACKEND (DO)
STEP 0 INVENTORY + registry REUSE (this phase): use CUT 1 verified-present ids. Bind them. Author only named GAPS. Do not invent a block id.
One FACTORY_CODE_CLI writer. No extra coder roles.
Write routes, handlers, and schema only.
Every required capability gets a one-record POST/GET round-trip (POST creates, GET returns it).
Honour reuse_accept / schema-accept / persist-accept. Do not skip BLOCK_DEFAULT_ACTIONS.
STOP / checkpoint after PHASE 1 acceptance. Do not start PHASE 2.

# PHASE 2 of 3 — FRONTEND + RAG (DO)
STEP 0 INVENTORY + registry REUSE (this phase): use CUT 1 verified-present ids. Bind them. Author named GAPS. When inventory names rag / dual_rag, HARD WRITE app/rag_routes.py ingest/query HTTP — those routes are not named GAPS and not persist POST/GET. Do not invent a block id.
One FACTORY_CODE_CLI writer. No extra coder roles.
UI on the working backend (frontend modules call the live POST/GET routes). Do not invent a second API.
RAG ingest/query where the inventory names a rag / dual_rag surface (capability id contains rag, or block id rag / dual_rag / rag_*) — otherwise do not invent a RAG surface.
When RAG is owed, ship these HTTP routes as quoted paths in app/**/*.py (not docs/rag JSON, not phase-1 persist POST/GET): ingest POST /v1/rag/ingest or POST /v1/steward/rag/ingest; query GET or POST /v1/rag/query or GET or POST /v1/steward/rag/query.
HARD WRITE app/rag_routes.py (Factory keep-path plants this file when the CLI miss-scopes work items to capability gaps_only): quoted POST /v1/rag/ingest and GET|POST /v1/rag/query — or the /v1/steward/rag/* twins. Acceptance cannot pass without those quoted paths in app/**/*.py.
A vector_search bind is reuse_accept — do not invent a second vector store. It is not a substitute for those ingest/query routes. dual_rag_estate_docs / dual_rag_sop one-record POST/GET is persist, not ingest/query.
STOP / checkpoint after PHASE 2 acceptance. Do not start PHASE 3.

# PHASE 3 of 3 — INTEGRATION + RENDER-READY (DO)
STEP 0 INVENTORY + registry REUSE (this phase): use CUT 1 verified-present ids. Bind them. Author only named GAPS. Do not invent a block id.
One FACTORY_CODE_CLI writer. No extra coder roles.
Package, boot, and integration: shippable tree that *would* deploy (Dockerfile + render.yaml + app/main.py).
render-ready is not live Render deploy and not Store Docker acceptance — those stay owner-gated.
Then existing TESTER / STORE_MANAGER. STOP / checkpoint after PHASE 3 acceptance.

Block scopes (from block.json; report-only until L2.2 flip — do not invent):
- workflow READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- database READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'database', 'scope': 'sql'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'database', 'scope': 'sql'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- validation READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}", "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- event_bus READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- queue READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'memory', 'scope': 'cache'}", "{'kind': 'queue', 'scope': 'jobs'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'queue', 'scope': 'jobs'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- audit READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'database', 'scope': 'sql'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'database', 'scope': 'sql'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- team READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'file', 'scope': 'local.read'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'team', 'scope': 'state'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'file', 'scope': 'local.write'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- formula_executor READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'network', 'scope': 'http.outbound'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=['(none)']
- recommendation_template READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'file', 'scope': 'local.read'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=['(none)']
- analytics READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'llm', 'scope': 'provider'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- capture READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'file', 'scope': 'local.read'}", "{'kind': 'file', 'scope': 'input_image'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'network', 'scope': 'http.outbound'}", "{'kind': 'llm', 'scope': 'provider'}", "{'kind': 'credential', 'scope': 'env'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'file', 'scope': 'local.write'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}", "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"]
- knowledge READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'network', 'scope': 'http.outbound'}", "{'kind': 'database', 'scope': 'vector'}", "{'kind': 'llm', 'scope': 'provider'}", "{'kind': 'credential', 'scope': 'env'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}", "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"]
- vector_search READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'database', 'scope': 'vector'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'database', 'scope': 'vector'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}", "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- notification READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'env', 'scope': 'process'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'network', 'scope': 'http.outbound'}", "{'kind': 'credential', 'scope': 'env'}", "{'kind': 'block', 'scope': 'peer'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'network', 'scope': 'smtp.outbound'}", "{'kind': 'email', 'scope': 'outbound'}", "{'kind': 'notification', 'scope': 'outbound'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}", "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"]
- dashboard READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]
- memory READS=["{'kind': 'caller', 'scope': 'input'}", "{'kind': 'config', 'scope': 'runtime'}", "{'kind': 'memory', 'scope': 'cache'}"] WRITES=["{'kind': 'caller', 'scope': 'output'}", "{'kind': 'memory', 'scope': 'cache'}"] NEVER=['(none)'] ACCEPTANCE=["{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"]

Kit manifests (Factory shelf + on-disk packs):
{
  "platform": {
    "blocks": [
      "analytics",
      "audit",
      "capture",
      "dashboard",
      "database",
      "event_bus",
      "formula_executor",
      "knowledge",
      "memory",
      "notification",
      "queue",
      "recommendation_template",
      "team",
      "validation",
      "vector_search",
      "workflow"
    ],
    "id": "platform",
    "name": "Platform",
    "product_blocks": [
      "analytics",
      "audit",
      "capture",
      "dashboard",
      "database",
      "event_bus",
      "formula_executor",
      "knowledge",
      "memory",
      "notification",
      "queue",
      "recommendation_template",
      "team",
      "validation",
      "vector_search",
      "workflow"
    ],
    "source": "brief-compiler",
    "vendored_blocks": {
      "analytics": "vendor/blocks/analytics",
      "audit": "vendor/blocks/audit",
      "capture": "vendor/blocks/capture",
      "dashboard": "vendor/blocks/dashboard",
      "database": "vendor/blocks/database",
      "event_bus": "vendor/blocks/event_bus",
      "formula_executor": "vendor/blocks/formula_executor",
      "knowledge": "vendor/blocks/knowledge",
      "memory": "vendor/blocks/memory",
      "notification": "vendor/blocks/notification",
      "queue": "vendor/blocks/queue",
      "recommendation_template": "vendor/blocks/recommendation_template",
      "team": "vendor/blocks/team",
      "validation": "vendor/blocks/validation",
      "vector_search": "vendor/blocks/vector_search",
      "workflow": "vendor/blocks/workflow"
    },
    "version": "1.0.0"
  },
  "private_estate_operations": {
    "artifacts": [],
    "author": "bopoadz-del",
    "blocks": {
      "estate_core": [
        "estate_registry",
        "estate_maintenance",
        "evidence_verifier",
        "readiness_engine",
        "portfolio_rollup"
      ],
      "platform_compose": [
        "database",
        "storage",
        "validation",
        "document_engine",
        "knowledge",
        "vector_search",
        "formula_executor",
        "audit",
        "notification",
        "workflow",
        "event_bus",
        "queue",
        "team",
        "dashboard",
        "analytics",
        "spec_analyzer",
        "recommendation_template",
        "capture"
      ]
    },
    "blueprint": "blueprints/steward/steward.v1.yaml",
    "capabilities": [
      "estate_registry",
      "estate_maintenance",
      "house_manual_sop",
      "vendor_budget",
      "preventive_maintenance",
      "staff_scheduling",
      "principal_dashboard",
      "property_onboarding",
      "dual_rag_sop",
      "dual_rag_estate_docs",
      "composed_ops_loop",
      "evidence_capture",
      "human_authority_gate"
    ],
    "connectors": {
      "honesty": "Smart-home/IoT integrations are PLACEHOLDER connectors only \u2014 honestly labeled not_implemented.",
      "implemented": [],
      "placeholders": [
        "cmms_stub",
        "iot_stub",
        "document_vault_stub",
        "smart_home_placeholder"
      ]
    },
    "container": {
      "class": "app.containers.private_estate_operations.PrivateEstateOperationsContainer",
      "default_chat_prompt": null
    },
    "core_modules": [],
    "data": [
      "fixtures/demo_estate.json"
    ],
    "demo_fixtures": "fixtures/demo_estate.json",
    "description": "Full Steward estate kit: registry, House Manual SOP, vendor/budget, preventive maintenance, staff scheduling, principal dashboard, onboarding, dual RAG with Postgres+FastEmbed pilot path + live oracle suite. IoT connectors are honest placeholders.",
    "dual_rag": {
      "layer_1": {
        "description": "House Manual / SOP / global standards corpus",
        "id": "sop_standards",
        "index": "steward_sop_v1"
      },
      "layer_2": {
        "description": "Per-estate documents, separately indexed",
        "id": "estate_documents",
        "index": "steward_estate_docs_v1"
      }
    },
    "id": "private_estate_operations",
    "install_requires": {
      "min_platform_version": "2.0.0",
      "python": ">=3.10"
    },
    "name": "Private Estate Operations",
    "price_cents": 0,
    "product_blocks": [
      "estate_maintenance",
      "estate_registry",
      "portfolio_rollup",
      "readiness_engine"
    ],
    "prompts": [],
    "source": "brief-compiler",
    "status": "available",
    "tags": [
      "domain",
      "estate",
      "steward",
      "certification"
    ],
    "vendored_blocks": {
      "estate_maintenance": "vendor/blocks/estate_maintenance",
      "estate_registry": "vendor/blocks/estate_registry",
      "portfolio_rollup": "vendor/blocks/portfolio_rollup",
      "readiness_engine": "vendor/blocks/readiness_engine"
    },
    "version": "1.3.0"
  }
}

REUSE records (present/reuse + reads/writes/never/acceptance):
{
  "analytics": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "analytics",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'llm', 'scope': 'provider'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "audit": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "audit",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'database', 'scope': 'sql'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'database', 'scope': 'sql'}"
    ]
  },
  "capture": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}",
      "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"
    ],
    "block_id": "capture",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'file', 'scope': 'local.read'}",
      "{'kind': 'file', 'scope': 'input_image'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'network', 'scope': 'http.outbound'}",
      "{'kind': 'llm', 'scope': 'provider'}",
      "{'kind': 'credential', 'scope': 'env'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'file', 'scope': 'local.write'}"
    ]
  },
  "dashboard": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "dashboard",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "database": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "database",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'database', 'scope': 'sql'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'database', 'scope': 'sql'}"
    ]
  },
  "estate_maintenance": {
    "acceptance": [],
    "block_id": "estate_maintenance",
    "never": [],
    "present": false,
    "reads": [],
    "scope_declared": false,
    "source": "registry/blocks",
    "writes": []
  },
  "estate_registry": {
    "acceptance": [],
    "block_id": "estate_registry",
    "never": [],
    "present": false,
    "reads": [],
    "scope_declared": false,
    "source": "registry/blocks",
    "writes": []
  },
  "event_bus": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "event_bus",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "formula_executor": {
    "acceptance": [],
    "block_id": "formula_executor",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'network', 'scope': 'http.outbound'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "knowledge": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}",
      "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"
    ],
    "block_id": "knowledge",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'network', 'scope': 'http.outbound'}",
      "{'kind': 'database', 'scope': 'vector'}",
      "{'kind': 'llm', 'scope': 'provider'}",
      "{'kind': 'credential', 'scope': 'env'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "memory": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "memory",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'memory', 'scope': 'cache'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'memory', 'scope': 'cache'}"
    ]
  },
  "notification": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}",
      "{'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}"
    ],
    "block_id": "notification",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'network', 'scope': 'http.outbound'}",
      "{'kind': 'credential', 'scope': 'env'}",
      "{'kind': 'block', 'scope': 'peer'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'network', 'scope': 'smtp.outbound'}",
      "{'kind': 'email', 'scope': 'outbound'}",
      "{'kind': 'notification', 'scope': 'outbound'}"
    ]
  },
  "portfolio_rollup": {
    "acceptance": [],
    "block_id": "portfolio_rollup",
    "never": [],
    "present": false,
    "reads": [],
    "scope_declared": false,
    "source": "registry/blocks",
    "writes": []
  },
  "queue": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "queue",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'memory', 'scope': 'cache'}",
      "{'kind': 'queue', 'scope': 'jobs'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'queue', 'scope': 'jobs'}"
    ]
  },
  "readiness_engine": {
    "acceptance": [],
    "block_id": "readiness_engine",
    "never": [],
    "present": false,
    "reads": [],
    "scope_declared": false,
    "source": "registry/blocks",
    "writes": []
  },
  "recommendation_template": {
    "acceptance": [],
    "block_id": "recommendation_template",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'file', 'scope': 'local.read'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "team": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "team",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'file', 'scope': 'local.read'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}",
      "{'kind': 'team', 'scope': 'state'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'file', 'scope': 'local.write'}"
    ]
  },
  "validation": {
    "acceptance": [
      "{'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}",
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "validation",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'config', 'scope': 'runtime'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  },
  "vector_search": {
    "acceptance": [
      "{'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}",
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "vector_search",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'database', 'scope': 'vector'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}",
      "{'kind': 'database', 'scope': 'vector'}"
    ]
  },
  "workflow": {
    "acceptance": [
      "{'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}"
    ],
    "block_id": "workflow",
    "never": [],
    "present": true,
    "reads": [
      "{'kind': 'caller', 'scope': 'input'}",
      "{'kind': 'env', 'scope': 'process'}",
      "{'kind': 'config', 'scope': 'runtime'}"
    ],
    "scope_declared": true,
    "source": "registry/blocks",
    "writes": [
      "{'kind': 'caller', 'scope': 'output'}"
    ]
  }
}

Domain pack (binding fields):
{
  "authoritative_calculations": [
    "none claimed beyond persisted fields"
  ],
  "core_business_workflows": [
    "one-record round-trip for booking_management",
    "one-record round-trip for property_management",
    "one-record round-trip for dynamic_pricing",
    "one-record round-trip for review_management",
    "one-record round-trip for analytics_dashboard",
    "one-record round-trip for notification_system",
    "one-record round-trip for search_recommendation"
  ],
  "data_sources": [
    "vendored Store blocks",
    "local sqlite"
  ],
  "demo_data_requirements": [
    "one persisted record per capability"
  ],
  "domain_acceptance_conditions": [
    "product boots",
    "own gates green",
    "one-record round-trip per capability",
    "envelope vocab open|in_progress|closed enforced by schema, not prose"
  ],
  "domain_purpose": "StayFlow is an all-in-one hotel booking and property management platform for independent hotels, boutique inns, and small hotel groups. It unifies real-time reservation management, room inventory and rate control, dynamic pricing, guest reviews, and operational analytics, while keeping staff and guests informed with automated notifications and AI-assisted search and recommendations.",
  "domain_rules": [
    "status vocabulary is schema-enforced: open, in_progress, closed",
    "reserved-keyword fields are refused"
  ],
  "high_impact_actions": [
    "create",
    "update",
    "delete"
  ],
  "mission": "StayFlow is an all-in-one hotel booking and property management platform for independent hotels, boutique inns, and small hotel groups. It unifies real-time reservation management, room inventory and rate control, dynamic pricing, guest reviews, and operational analytics, while keeping staff and guests informed with automated notifications and AI-assisted search and recommendations.",
  "primary_users": [
    "hospitality operators"
  ],
  "prohibited_autonomous_actions": [
    "deploy",
    "store publish",
    "export when the pilot suite is red"
  ],
  "required_exports": [
    "pilot_candidate zip after PRODUCT+STORE green"
  ],
  "required_product_modules": [
    "booking_management",
    "property_management",
    "dynamic_pricing",
    "review_management",
    "analytics_dashboard",
    "notification_system",
    "search_recommendation"
  ],
  "required_roles": [
    "operator",
    "admin"
  ],
  "security_regulatory_rules": [
    "offline platform \u2014 no network, no HTTP store callbacks"
  ]
}

Done when (from intake blueprint):
- product boots
- own gates green
- one-record round-trip per capability
- envelope vocab open|in_progress|closed enforced by schema, not prose


==================================================
ACCEPTANCE (harness, not the coder)
==================================================

Fails loud. The run is not done until ALL of these are true. ACCEPTANCE is run by the harness, not the coder.
- the product boots  [check:boot]
- own gates green  [check:gates]
- one-record round-trip per capability (POST creates, GET returns it)  [check:round_trip]
- every emitted capability persists one record to its alembic entity and GET returns it (post-boot: the pilot-marked tests against the booted product, and a one-record round-trip per capability (POST creates, GET returns it))  [check:round_trip]
- every capability accepts a POST built from its own FIELDS/CONSTRAINTS (writer_behaviour baseline)  [check:writer_behaviour]
- every REUSE keep-path handler accepts a schema-sample POST without Unknown action / Unknown action: None (post-boot: the pilot-marked tests against the booted product, and a one-record round-trip per capability (POST creates, GET returns it))  [check:reuse_accept]
- PRODUCT accept-payload (booking_management, notification_system): every event_bus step including step_0 (automated_reminders class), step_1 (appointment_scheduling class) and step_2+ (appointment_booking class) accepts the prepared contract (topic, payload dict, message, channel=mcp, action=publish) — never the raw schema sample (test_every_capability_route_accepts_payload; workflow: step_N (event_bus): error; workflow: step_0 (event_bus): error; workflow: step_1 (event_bus): error; workflow: step_2 (event_bus): error)  [check:event_bus_workflow]
- the domain pack's domain_acceptance_conditions hold  [check:domain_acceptance]
- envelope vocab open, in_progress, closed enforced by schema, not prose  [check:envelope_schema]
- PRODUCT gate: post-boot: the pilot-marked tests against the booted product, and a one-record round-trip per capability (POST creates, GET returns it)  [check:product_gate]
- STORE gate: scripts/acceptance.py (≥12 measured checks) inside the Store-built Docker image — k/k required; restart-survival of the booted store; authorship floor is not acceptance  [check:store_gate]
- scripts/acceptance.py ≥12 measured checks k/k inside the Store-built image  [check:store_acceptance]
- ledger records pilot_ready=true  [check:ledger]
- launching-ready full-pilot authorship: ≥5 keepable agent-written app/actions/*.py handlers (or equivalent cli_authored_ids)  [check:full_pilot_authorship]
- PHASE 1 of 3 BACKEND accepted: routes/handlers/schema and one-record POST/GET per required capability  [check:writer_phase_backend]
- PHASE 2 of 3 FRONTEND + RAG accepted: UI on working backend; RAG ingest/query where needed — POST /v1/rag/ingest or POST /v1/steward/rag/ingest plus GET|POST /v1/rag/query or GET|POST /v1/steward/rag/query in app/**/*.py  [check:writer_phase_frontend_rag]
- PHASE 3 of 3 INTEGRATION accepted: package/boot/render-ready (not live Render; not Store Docker)  [check:writer_phase_integration]
- fail-closed: phase N acceptance before phase N+1 dispatch  [check:writer_phase_gate]
- resume skips landed writer phases (do not redo completed earlier phases from zero)  [check:writer_phase_resume]

The harness's acceptance IS the tester. Do not write decorative tests. Do not treat thin SUCCESS / templates-only / stubbed capabilities / authorship below the launching-ready full-pilot floor as done.

Block-level acceptance (from block.json, report-only until flip):
- formula_executor: (none declared)  [check:block_acceptance]
- database: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- vector_search: {'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}, {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- capture: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}, {'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}  [check:block_acceptance]
- queue: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- workflow: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- recommendation_template: (none declared)  [check:block_acceptance]
- analytics: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- memory: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- team: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- validation: {'id': 'missing_required_input', 'check': 'refuses or errors when a required input is absent', 'status': 'refused'}, {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- audit: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- notification: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}, {'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}  [check:block_acceptance]
- dashboard: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- event_bus: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}  [check:block_acceptance]
- knowledge: {'id': 'unknown_action', 'check': 'errors on an unknown or missing action', 'status': 'failed'}, {'id': 'missing_credential', 'check': 'fails loud when a required credential or key is absent', 'status': 'failed'}  [check:block_acceptance]


==================================================
FORBIDDEN
==================================================

- HARD RULE: sealed vendor is read-only — do not write vendor/**, vendor_blocks/**, vendor_blocks_mirror/**, blocks.lock.json, build_ledger.jsonl, .git/**, or anything under SEALED_AFTER_CLONER; implement domain in app/** and tests/** only as allowed by ba_allowed_globs / Hybrid C for BA; prefer docs/openapi.json and root openapi.json only — never vendor/**; never patch vendored blocks — call Store blocks via execute(action=)
- thin SUCCESS (code-cycle green, pilot_ready=false)
- authorship below the launching-ready full-pilot floor (<5 agent-written app/actions/*.py / cli_authored_ids) — FACTORY_CODE_CLI_THIN_AUTHORSHIP
- decorative tests
- reserved-keyword fields (action inside the payload dict, id as a domain field)
- unlisted blocks (ids not in the Store registry / inventory)
- assuming a REUSE id is present when STEP 0 flagged it missing
- claiming REUSE without a loadable app/actions/{capability_id}.py handler source
- inventing READS/WRITES/NEVER/ACCEPTANCE when block.json has not declared them
- inventing a stricter accept-contract than the spec (writer_behaviour schema-accept)
- eager from app.actions import re-exports in app/actions/__init__.py (circular import; writer_behaviour workspace does not import)
- importing app.actions / app.routes / app.main from a capability handler (writer_behaviour workspace does not import)
- persist to a table alembic 0001 did not create (no such table: <entity>)
- leaving PRODUCT on a leftover ./data/platform.db stamped at 0001_baseline after the factory rewrote 0001 (upgrade_head no-op)
- execute(block_id, payload) or no_block_bound stubs that never store.save(ENTITY, payload) (keyword-fallback audit / dashboard / {vertical}_core class)
- persist to table=records or to the capability id when spec.entity is a different name
- treating WRITER writer_behaviour green on a tempfile DB as done while PRODUCT still did not remember a record they were given
- execute(block_id, payload) or action=None (Unknown action: None)
- empty BLOCK_DEFAULT_ACTIONS on a REUSE handler that binds Store blocks
- burying action inside the payload dict
- reaching TESTER PRODUCT with Unknown action or workflow: step_0 (event_bus): error after keep-path emit
- omitting workflow input['result'] so PRODUCT fails as workflow: RuntimeError: 'result' (accept-payload persisted nothing)
- rewriting name['result'] = into name.get(...) = so PRODUCT fails as SyntaxError: cannot assign to function call (queue / formula_executor Store shims assign that key)
- fail-closed keeping the whole original module so PRODUCT fails as workflow: RuntimeError: 'result' (fail-closed keep original must still rewrite reads)
- forwarding the PRODUCT schema sample as an event_bus workflow step input
- setting an event_bus workflow step to 'input': payload or "input": payload (or input=dict(payload))
- an unprepared step_0 (event_bus) — Store 0-index first child; automated_reminders class fails PRODUCT as workflow: step_0 (event_bus): error
- an unprepared step_1 (event_bus) — appointment_scheduling class fails PRODUCT as workflow: step_1 (event_bus): error
- a prepared step_1 plus an unprepared step_2 (event_bus) — appointment_booking class still fails PRODUCT as workflow: step_2 (event_bus): error
- treating one prepared event_bus child, a prepare_block_input import, or the factory execute wrap as keep/done while any child (including step_1) is still raw
- channel=sample or channel=email without `to` on an event_bus step (use channel=mcp)
- inventing workflow: step_N (event_bus): error / workflow: step_0 (event_bus): error / workflow: step_1 (event_bus): error / workflow: step_2 (event_bus): error without the prepared contract on EVERY event_bus child (topic, payload dict, message, channel=mcp, action=publish)
- execute(block_id, payload) stubs for appointment / booking / reminder capabilities (WRITER must emit the factory-grounded prepared event_bus step)
- execute("workflow", payload) with the raw schema sample
- omitting workflow input['result'] so PRODUCT fails as workflow: RuntimeError: 'result' (schema-sample POST has no result key; Store kit shim wraps KeyError as RuntimeError)
- rewriting name['result'] = into name.get(...) = so PRODUCT fails as SyntaxError: cannot assign to function call (queue / formula_executor Store shims)
- fail-closed keeping the whole original module so PRODUCT fails as workflow: RuntimeError: 'result' (fail-closed keep original must still rewrite reads)
- one handle() / one spec / one route at a time — this brief is the whole job
- starting PHASE N+1 before PHASE N acceptance [check:writer_phase_gate]
- redoing a landed writer phase from zero [check:writer_phase_resume]
- extra coder roles — one FACTORY_CODE_CLI writer
- treating PHASE 3 render-ready as live Render deploy or Store Docker acceptance
- weakening honesty or exporting when the pilot suite is red

