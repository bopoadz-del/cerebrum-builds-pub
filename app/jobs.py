# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['validation', 'config', 'version', 'auth', 'notification', 'email', 'database', 'orchestrator', 'knowledge', 'memory', 'audit', 'governance_gate', 'formula_executor', 'evidence_chain', 'ingestion_provenance', 'analytics', 'pdf', 'dashboard', 'workflow', 'approval_rules', 'transaction_state_machine', 'version_diff', 'workbench', 'vector_search'], 'gaps': [], 'bindings': [{'capability_id': 'track_loader', 'block_ids': ['validation', 'config', 'version'], 'gap': False}, {'capability_id': 'enrolment_and_calendar', 'block_ids': ['auth', 'notification', 'email', 'database'], 'gap': False}, {'capability_id': 'faculty_session', 'block_ids': ['orchestrator', 'knowledge', 'memory', 'audit', 'governance_gate'], 'gap': False}, {'capability_id': 'memo_grading', 'block_ids': ['formula_executor', 'validation', 'evidence_chain', 'ingestion_provenance'], 'gap': False}, {'capability_id': 'gradebook_and_transcript', 'block_ids': ['analytics', 'pdf', 'database', 'dashboard'], 'gap': False}, {'capability_id': 'defense_and_capstone', 'block_ids': ['workflow', 'notification', 'approval_rules', 'transaction_state_machine', 'pdf'], 'gap': False}, {'capability_id': 'track_admin', 'block_ids': ['validation', 'version_diff', 'workbench', 'audit'], 'gap': False}, {'capability_id': 'reading_and_case_library', 'block_ids': ['knowledge', 'vector_search', 'governance_gate'], 'gap': False}], 'agent_reviews': [{'capability_id': 'track_loader', 'block_ids': ['validation', 'config', 'version'], 'verdict': 'endorse', 'reason': 'Validation pipeline plus config and version management plausibly serve loading/tracking curriculum assets with versioned, validated content.'}, {'capability_id': 'enrolment_and_calendar', 'block_ids': ['auth', 'notification', 'email', 'database'], 'verdict': 'endorse', 'reason': 'Auth for enrolment, database for records, email/notification for confirmations; no calendar-specific block but general store+notify is plausible.'}, {'capability_id': 'faculty_session', 'block_ids': ['orchestrator', 'knowledge', 'memory', 'audit', 'governance_gate'], 'verdict': 'endorse', 'reason': 'Orchestration, RAG knowledge, session cache, audit, and governance gate fit faculty session lifecycle and oversight well.'}, {'capability_id': 'memo_grading', 'block_ids': ['formula_executor', 'validation', 'evidence_chain', 'ingestion_provenance'], 'verdict': 'endorse', 'reason': 'Formula execution, validation, tamper-evident evidence chain, and ingestion provenance strongly serve grading with traceability.'}, {'capability_id': 'gradebook_and_transcript', 'block_ids': ['analytics', 'pdf', 'database', 'dashboard'], 'verdict': 'endorse', 'reason': 'Database for grades, analytics/dashboard for reporting, PDF extraction for transcripts—coherent fit.'}, {'capability_id': 'defense_and_capstone', 'block_ids': ['workflow', 'notification', 'approval_rules', 'transaction_state_machine', 'pdf'], 'verdict': 'mismatch', 'reason': 'Approval_rules (clearance-rule review) and marketplace transaction_state_machine are strained fits for a capstone/defense workflow; workflow/notification/pdf carry it.'}, {'capability_id': 'track_admin', 'block_ids': ['validation', 'version_diff', 'workbench', 'audit'], 'verdict': 'endorse', 'reason': 'Validation, version diff, bounded workbench, and audit plausibly serve admin review and change control.'}, {'capability_id': 'reading_and_case_library', 'block_ids': ['knowledge', 'vector_search', 'governance_gate'], 'verdict': 'endorse', 'reason': 'RAG knowledge, semantic vector search, and governance gate fit a searchable, access-controlled reading/case library.'}], 'agent_model': 'deepseek-chat'}


CAPABILITIES = []


GATES = {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'runs_over_http': False, 'suite': [{'file': 'tests/test_smoke.py', 'covers': 'import, offline dispatch load, handle() returns a mapping', 'gated': True}, {'file': 'tests/test_smoke.py', 'covers': 'Store-backed handle() ok and nested error scan', 'marker': 'pilot', 'gated': False}, {'file': 'tests/test_models.py', 'covers': 'sqlite round-trip via store.save / store.get', 'gated': True}, {'file': 'tests/test_data_lifecycle.py', 'covers': 'Alembic up/down on populated v1, restore drill, parallel writes', 'gated': True}, {'file': 'tests/test_deploy.py', 'covers': 'Fail-closed /health, correlation logs, revision rollback identity', 'gated': True}, {'file': 'tests/test_domain_acceptance.py', 'covers': 'Ten business outcomes through execute_action', 'marker': 'pilot', 'gated': False}, {'file': 'tests/test_routes.py', 'covers': 'HTTP 200 JSON for /health, kernel jobs, and each capability POST', 'gated': True}, {'file': 'tests/test_routes.py', 'covers': 'Store-backed POST accepted (ok is not False) and persisted', 'marker': 'pilot', 'gated': False}, {'file': 'tests/agent_domain_cases.py', 'covers': 'optional coding-agent domain mutations of spec payloads', 'optional': True, 'gated': False}]}


def _read_workspace_json(relative: str) -> Optional[Dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / relative
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _job(kernel: str) -> Dict[str, Any]:
    for item in JOBS:
        if item['kernel'] == kernel:
            return dict(item)
    return {'kernel': kernel}


def inventory() -> Dict[str, Any]:
    payload = _job('CLONER')
    payload['lock'] = _read_workspace_json('blocks.lock.json') or {
        'schema': 'blocks.lock.v1',
        'blocks': {},
    }
    return payload


def provenance() -> Dict[str, Any]:
    payload = _job('STORE_MANAGER')
    payload['build'] = _read_workspace_json('docs/build_provenance.json') or {}
    lock = _read_workspace_json('blocks.lock.json') or {}
    payload['clones'] = lock.get('blocks') or {}
    payload['store_ops'] = []
    return payload
# --- END factory block ---
