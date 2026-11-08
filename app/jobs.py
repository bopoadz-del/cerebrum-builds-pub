"""The kernel roster and this platform's capability manifest.

The five kernel jobs are the factory roles this platform is manufactured
under; the capability entries are the platform's own, each with the store
entity it persists and the Store blocks it drives.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import sources
from app.models import MODELS

CAPABILITY_BLOCKS: Dict[str, List[str]] = {
    "contract_source_of_record": [
        "pdf", "ocr", "knowledge", "document_engine", "vector_search",
        "audit_chain",
    ],
    "progress_claims": [
        "boq_processor", "finance_canonical_model", "formula_executor",
        "workflow", "approval_rules", "pdf", "transaction_state_machine",
    ],
    "delay_damages_tracking": [
        "cpm_engine", "formula_executor", "notification", "analytics",
        "dashboard",
    ],
    "qa_itp_records": [
        "workflow", "approval_rules", "evidence_chain", "capture",
        "document_engine", "audit",
    ],
    "document_register": [
        "document_engine", "version", "file_hasher", "audit_chain", "search",
        "notification",
    ],
    "contract_compliance_gate": [
        "validation", "governance_gate", "evidence_or_refuse",
        "rule_intent_router", "audit_fail_closed",
    ],
}

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": cap_id,
        "capability_id": cap_id,
        "entity": getattr(cls, "ENTITY", cap_id),
        "block_ids": list(CAPABILITY_BLOCKS.get(cap_id, [])),
    }
    for cap_id, cls in sorted(MODELS.items())
]

JOBS = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store registry and bind verified block ids to each capability.",
        "http_routes": ["GET /v1/catalog", "GET /v1/capabilities"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Stock the vendored blocks in the platform tree and pin their paths.",
        "http_routes": ["GET /v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author routes, handlers, schema and the operator console.",
        "http_routes": ["POST /v1/{capability_id}", "GET /v1/{capability_id}"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the platform gate; a gate that did not run is not a pass.",
        "http_routes": ["GET /v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Record provenance and the store acceptance result.",
        "http_routes": ["GET /v1/provenance"],
        "agent": "store-manager",
    },
]

CATALOG: Dict[str, Any] = {
    "kernel": "COLLECTOR",
    "platform_id": "harbourline",
    "name": sources.PROJECT_NAME,
    "bindings": [
        {
            "capability_id": item["capability_id"],
            "entity": item["entity"],
            "block_ids": item["block_ids"],
            "gap": False,
            "strategy": "REUSE",
        }
        for item in CAPABILITIES
    ],
}

GATES: Dict[str, Any] = {
    "kernel": "TESTER",
    "runs_over_http": False,
    "gates": [
        {"id": "code", "suite": 'pytest -m "not pilot"'},
        {"id": "pilot", "suite": "pytest -m pilot"},
        {"id": "store", "suite": "scripts/acceptance.py"},
    ],
    "fail_closed": True,
}


def inventory() -> Dict[str, Any]:
    return {
        "kernel": "CLONER",
        "lock": {
            "path": "blocks.lock.json",
            "sealed": True,
            "blocks": sorted({b for ids in CAPABILITY_BLOCKS.values() for b in ids}),
        },
        "items": [
            {"block_id": block_id, "capability_id": cap_id, "path": "vendor/blocks/%s" % block_id}
            for cap_id, blocks in sorted(CAPABILITY_BLOCKS.items())
            for block_id in blocks
        ],
    }


def provenance() -> Dict[str, Any]:
    return {
        "kernel": "STORE_MANAGER",
        "platform_id": "harbourline",
        "name": sources.PROJECT_NAME,
        "capabilities": [item["capability_id"] for item in CAPABILITIES],
        "entities": {item["capability_id"]: item["entity"] for item in CAPABILITIES},
        "blocks": sorted({b for ids in CAPABILITY_BLOCKS.values() for b in ids}),
    }
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['pdf', 'ocr', 'knowledge', 'document_engine', 'vector_search', 'audit_chain', 'boq_processor', 'finance_canonical_model', 'formula_executor', 'workflow', 'approval_rules', 'transaction_state_machine', 'cpm_engine', 'notification', 'analytics', 'dashboard', 'evidence_chain', 'capture', 'audit', 'version', 'file_hasher', 'search', 'validation', 'governance_gate', 'evidence_or_refuse', 'rule_intent_router', 'audit_fail_closed'], 'gaps': [], 'bindings': [{'capability_id': 'contract_source_of_record', 'block_ids': ['pdf', 'ocr', 'knowledge', 'document_engine', 'vector_search', 'audit_chain'], 'gap': False}, {'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'finance_canonical_model', 'formula_executor', 'workflow', 'approval_rules', 'pdf', 'transaction_state_machine'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'notification', 'analytics', 'dashboard'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['workflow', 'approval_rules', 'evidence_chain', 'capture', 'document_engine', 'audit'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'file_hasher', 'audit_chain', 'search', 'notification'], 'gap': False}, {'capability_id': 'contract_compliance_gate', 'block_ids': ['validation', 'governance_gate', 'evidence_or_refuse', 'rule_intent_router', 'audit_fail_closed'], 'gap': False}], 'agent_reviews': [{'capability_id': 'contract_source_of_record', 'block_ids': ['pdf', 'ocr', 'knowledge', 'document_engine', 'vector_search', 'audit_chain'], 'verdict': 'endorse', 'reason': 'Ingest (pdf/ocr), parse and structure (document_engine), retrieve (vector_search/knowledge) and tamper-evident chain for the source of record all match the capability.'}, {'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'finance_canonical_model', 'formula_executor', 'workflow', 'approval_rules', 'pdf', 'transaction_state_machine'], 'verdict': 'endorse', 'reason': 'BOQ parsing plus formula execution and named-approval gating with a fail-closed lifecycle state machine is a plausible fit for progress-claim assessment and adjudication.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'notification', 'analytics', 'dashboard'], 'verdict': 'endorse', 'reason': 'CPM schedule analysis (float, critical path, compression) with formula execution and analytics/dashboard reporting directly serves delay and damages tracking.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['workflow', 'approval_rules', 'evidence_chain', 'capture', 'document_engine', 'audit'], 'verdict': 'endorse', 'reason': 'Capture and document parsing for inspection/test records, named approval, evidence chain and audit align with ITP records and sign-off.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'file_hasher', 'audit_chain', 'search', 'notification'], 'verdict': 'mismatch', 'reason': "Register basics (document parse, versioning, hashing, audit chain) fit, but the bundled 'search' block is external DuckDuckGo/Serper web search and is not a document-register indexing/search capability — strained for tender review."}, {'capability_id': 'contract_compliance_gate', 'block_ids': ['validation', 'governance_gate', 'evidence_or_refuse', 'rule_intent_router', 'audit_fail_closed'], 'verdict': 'mismatch', 'reason': "Governance gate, evidence-or-refuse, validation and fail-closed audit fit, but 'rule_intent_router' is a $TICKER/regex chat intent ladder from a trading bot — unrelated to contract compliance and would be flagged."}], 'agent_model': 'deepseek-chat'}


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
