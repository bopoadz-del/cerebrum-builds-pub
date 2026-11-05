"""Capability manifest read by the factory harness and the console."""

from __future__ import annotations

CAPABILITIES = [
    {
        "id": "progress_claim_administration",
        "entity": "progress_claim_administration",
        "title": "Progress claims",
        "description": "Interim payment certificates priced against the BOQ, with Clause 14.3 retention and Clause 4.2 performance security.",
        "blocks": ["boq_processor", "finance_reconciliation", "approval_rules"],
    },
    {
        "id": "delay_damages_tracking",
        "entity": "delay_damages_tracking",
        "title": "Delay damages",
        "description": "Clause 8.7 position: 0.1% per day capped at 10% of the Accepted Contract Amount.",
        "blocks": ["formula_executor", "validation"],
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA / ITP records",
        "description": "Inspection and test plan records linked to BOQ items and contract requirements.",
        "blocks": ["document_engine", "workflow"],
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "description": "Controlled register of contract, BOQ and drawing revisions with search and checksum provenance.",
        "blocks": ["document_engine", "search", "version"],
    },
]

CAPABILITY_IDS = [item["id"] for item in CAPABILITIES]
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['boq_processor', 'finance_reconciliation', 'approval_rules', 'formula_executor', 'validation', 'document_engine', 'workflow', 'search', 'version'], 'gaps': [], 'bindings': [{'capability_id': 'progress_claim_administration', 'block_ids': ['boq_processor', 'finance_reconciliation', 'approval_rules'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'validation'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'workflow'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'search', 'version'], 'gap': False}], 'agent_reviews': [{'capability_id': 'progress_claim_administration', 'block_ids': ['boq_processor', 'finance_reconciliation', 'approval_rules'], 'verdict': 'endorse', 'reason': 'BOQ parsing, decimal-safe reconciliation and per-item named approval with ledger plausibly cover claim measurement, valuation and sign-off.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'validation'], 'verdict': 'mismatch', 'reason': 'formula_executor handles construction formulas but validation is block-store certification, not contractual delay/damages rules, notice periods or schedule evidence; no event or time-tracking logic is bound.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'workflow'], 'verdict': 'endorse', 'reason': 'Document parse/reason/map plus chained workflow plausibly produce and route inspection and test plan records.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'search', 'version'], 'verdict': 'mismatch', 'reason': 'version block is software release versioning, and search is public web lookup; neither provides controlled-document revision register or transmittal governance a register demands.'}], 'agent_model': 'deepseek-chat'}


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
