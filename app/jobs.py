"""The platform's capability roster and the kernel job descriptions.

These are the product's own data: which capabilities the platform runs, which
blocks each binds, and the five kernel roles the operator can inspect. The
routes publish them; nothing here decides a domain outcome.
"""

from __future__ import annotations

from typing import Any, Dict, List

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "track_management",
        "entity": "track_management",
        "title": "Track management",
        "blocks": ["validation", "validation_pipeline_fork", "spec_analyzer", "workflow", "workbench", "audit"],
        "summary": "Upload, validate and version 16-week track YAML against track.v1; week-level diff; pin a version per enrolment.",
    },
    {
        "id": "enrolment_and_scheduling",
        "entity": "enrolment_and_scheduling",
        "title": "Enrolment and scheduling",
        "blocks": ["workflow", "cpm_engine", "team", "notification", "email", "transaction_state_machine"],
        "summary": "Enrol a learner and expand the fixed 16x6 session template into a dated, timezone-aware schedule.",
    },
    {
        "id": "ai_faculty_sessions",
        "entity": "ai_faculty_sessions",
        "title": "AI faculty sessions",
        "blocks": ["agent_swarm", "sub_agent_runtime", "knowledge", "memory", "audit_chain"],
        "summary": "Per-session faculty chat in one of six kernel modes, with one audit row per session.",
    },
    {
        "id": "memo_grading",
        "entity": "memo_grading",
        "title": "Memo grading",
        "blocks": ["formula_executor", "evidence_chain", "evidence_verifier", "answer_quality_scorer", "audit_chain", "validation"],
        "summary": "Independent grader: five criteria 0-20, formula total, band, verdicts, provenance; re-sit under 70.",
    },
    {
        "id": "gradebook_and_transcript",
        "entity": "gradebook_and_transcript",
        "title": "Gradebook and transcript",
        "blocks": ["analytics", "dashboard", "pdf", "audit"],
        "summary": "Live weighted average (memos 60, defenses 20, capstone 20) and a transcript PDF carrying every grade.",
    },
    {
        "id": "defenses_and_capstone",
        "entity": "defenses_and_capstone",
        "title": "Defenses and capstone",
        "blocks": ["workflow", "approval_rules", "email", "notification", "transaction_state_machine"],
        "summary": "Term defense with a 7-day re-sit window, two invited reviewers, three verdicts, and the graduation rule.",
    },
    {
        "id": "library_surfaces",
        "entity": "library_surfaces",
        "title": "Library surfaces",
        "blocks": ["reference_corpus", "search", "knowledge", "vector_search"],
        "summary": "Per-week readings and public sources; case outcomes revealed only in the case_class session.",
    },
    {
        "id": "command_center_and_chat",
        "entity": "command_center_and_chat",
        "title": "Command centre and chat",
        "blocks": ["dashboard", "voice", "aesthetic_kit"],
        "summary": "Operator console over enrol -> today -> session -> submit -> gradebook, at desktop and phone width.",
    },
]

KERNEL_JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store for blocks that cover the brief and name each one by its verified id.",
        "http_routes": ["GET /v1/catalog"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Pin every bound block to one locked path in the product tree and refuse a tree that drifts from the lock.",
        "http_routes": ["GET /v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author routes, handlers and schema for every capability, with no stub on auth, tenancy, retrieval, formulas or export.",
        "http_routes": ["POST /v1/{capability_id}"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the acceptance floor over the booted product and refuse a green bought by removing a check.",
        "http_routes": ["GET /v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Record what shipped, its block provenance and its acceptance evidence for the buyer.",
        "http_routes": ["GET /v1/provenance"],
        "agent": "store_manager",
    },
]

ORDERS: List[Dict[str, str]] = [
    {"stage": "enrol", "capability": "enrolment_and_scheduling"},
    {"stage": "today", "capability": "enrolment_and_scheduling"},
    {"stage": "session", "capability": "ai_faculty_sessions"},
    {"stage": "submit", "capability": "memo_grading"},
    {"stage": "gradebook", "capability": "gradebook_and_transcript"},
]

CAPABILITY_BY_ID: Dict[str, Dict[str, Any]] = {item["id"]: item for item in CAPABILITIES}
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['aesthetic_kit', 'agent_swarm', 'analytics', 'answer_quality_scorer', 'approval_rules', 'audit', 'audit_chain', 'cpm_engine', 'dashboard', 'email', 'evidence_chain', 'evidence_verifier', 'formula_executor', 'knowledge', 'memory', 'notification', 'pdf', 'reference_corpus', 'search', 'spec_analyzer', 'sub_agent_runtime', 'team', 'transaction_state_machine', 'validation', 'validation_pipeline_fork', 'vector_search', 'voice', 'workbench', 'workflow'], 'gaps': [], 'bindings': [{'capability_id': 'track_management', 'block_ids': ['validation', 'validation_pipeline_fork', 'spec_analyzer', 'workflow', 'workbench', 'audit'], 'gap': False}, {'capability_id': 'enrolment_and_scheduling', 'block_ids': ['workflow', 'cpm_engine', 'team', 'notification', 'email', 'transaction_state_machine'], 'gap': False}, {'capability_id': 'ai_faculty_sessions', 'block_ids': ['agent_swarm', 'sub_agent_runtime', 'knowledge', 'memory', 'audit_chain'], 'gap': False}, {'capability_id': 'memo_grading', 'block_ids': ['formula_executor', 'evidence_chain', 'evidence_verifier', 'answer_quality_scorer', 'audit_chain', 'validation'], 'gap': False}, {'capability_id': 'gradebook_and_transcript', 'block_ids': ['analytics', 'dashboard', 'pdf', 'audit'], 'gap': False}, {'capability_id': 'defenses_and_capstone', 'block_ids': ['workflow', 'approval_rules', 'email', 'notification', 'transaction_state_machine'], 'gap': False}, {'capability_id': 'library_surfaces', 'block_ids': ['reference_corpus', 'search', 'knowledge', 'vector_search'], 'gap': False}, {'capability_id': 'command_center_and_chat', 'block_ids': ['dashboard', 'voice', 'aesthetic_kit'], 'gap': False}], 'agent_reviews': [], 'agent_model': ''}


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
