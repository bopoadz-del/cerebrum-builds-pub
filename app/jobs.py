"""Kernel job roster and the capability manifest.

The roster is the factory ladder this platform was manufactured by; the
manifest is what the product serves. Both are read by /v1/jobs,
/v1/catalog, /v1/inventory and /v1/capabilities.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_terms as terms
from app import models

BLOCKS: List[str] = [
    "analytics", "approval_rules", "audit_chain", "boq_processor", "cpm_engine",
    "dashboard", "document_engine", "evidence_chain", "evidence_or_refuse",
    "evidence_verifier", "file_hasher", "finance_canonical_model",
    "finance_reconciliation_workflow", "formula_executor", "knowledge",
    "notification", "review", "search", "transaction_state_machine",
    "vector_search", "version_diff", "workflow",
]

KITS: List[Dict[str, Any]] = [
    {"id": "platform", "name": "Platform", "version": "1.0.0", "blocks": BLOCKS},
]

LOCK: Dict[str, Any] = {
    "file": "blocks.lock.json",
    "blocks": {block: {"path": "vendor/blocks/%s" % block} for block in BLOCKS},
}

GATE_CHECKS: List[Dict[str, Any]] = [
    {"id": "boot", "description": "the product boots"},
    {"id": "round_trip", "description": "one-record POST/GET per capability"},
    {"id": "writer_behaviour", "description": "every capability accepts its own schema sample"},
    {"id": "reuse_accept", "description": "every bound block is invoked and accepts its input"},
    {"id": "fail_closed", "description": "a failed block is a refusal, never ok:true"},
]

JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store and bind the exact blocks a capability needs.",
        "http_routes": ["/v1/catalog", "/v1/capabilities"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Vendor the locked blocks and pin every one to a single path.",
        "http_routes": ["/v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author the handlers, routes, models and console that serve them.",
        "http_routes": ["/v1/formulas", "/v1/rag/ingest", "/v1/rag/query"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the gates and refuse a build that fails its own contract.",
        "http_routes": ["/v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Record provenance and register the finished platform.",
        "http_routes": ["/v1/provenance"],
        "agent": "store_manager",
    },
]

CAPABILITY_META: Dict[str, Dict[str, str]] = {
    "progress_claim_processing": {
        "title": "Progress claims",
        "summary": "Assess Interim Payment Certificates against the BOQ with Clause 14.3 retention.",
    },
    "delay_damages_tracking": {
        "title": "Delay damages",
        "summary": "Track Time for Completion and compute Clause 8.7 delay damages against the cap.",
    },
    "qa_itp_records": {
        "title": "QA / ITP records",
        "summary": "Record inspections, hold points and sign-offs linked to BOQ items and documents.",
    },
    "document_register": {
        "title": "Document register",
        "summary": "Hash, version and clause-link every controlled project document.",
    },
    "contract_clause_grounding": {
        "title": "Contract clause grounding",
        "summary": "Answer questions from the contract and BOQ corpus, refusing when evidence is thin.",
    },
    "performance_security_tracking": {
        "title": "Performance security",
        "summary": "Track the Clause 4.2 security, its cover and its renewal window.",
    },
    "compliance_dashboard": {
        "title": "Compliance dashboard",
        "summary": "One view of claims, delay exposure, ITP completion, documents and security.",
    },
}

CAPABILITY_BLOCKS: Dict[str, List[str]] = {
    "progress_claim_processing": ["boq_processor", "finance_canonical_model", "finance_reconciliation_workflow", "approval_rules", "document_engine"],
    "delay_damages_tracking": ["cpm_engine", "formula_executor", "evidence_chain", "transaction_state_machine"],
    "qa_itp_records": ["workflow", "review", "document_engine", "audit_chain"],
    "document_register": ["document_engine", "file_hasher", "version_diff", "audit_chain"],
    "contract_clause_grounding": ["knowledge", "vector_search", "evidence_or_refuse", "evidence_verifier"],
    "performance_security_tracking": ["workflow", "notification", "audit_chain"],
    "compliance_dashboard": ["dashboard", "analytics", "notification"],
}

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": capability_id,
        "entity": cls.ENTITY,
        "title": CAPABILITY_META.get(capability_id, {}).get("title", capability_id),
        "summary": CAPABILITY_META.get(capability_id, {}).get("summary", ""),
        "blocks": list(CAPABILITY_BLOCKS.get(capability_id, [])),
        "fields": list(cls.FIELDS),
        "source": "document:%s" % terms.CONTRACT_FILENAME,
    }
    for capability_id, cls in models.MODELS.items()
]
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['boq_processor', 'finance_canonical_model', 'finance_reconciliation_workflow', 'approval_rules', 'document_engine', 'cpm_engine', 'formula_executor', 'evidence_chain', 'transaction_state_machine', 'workflow', 'review', 'audit_chain', 'file_hasher', 'version_diff', 'search', 'knowledge', 'vector_search', 'evidence_or_refuse', 'evidence_verifier', 'notification', 'dashboard', 'analytics'], 'gaps': [], 'bindings': [{'capability_id': 'progress_claim_processing', 'block_ids': ['boq_processor', 'finance_canonical_model', 'finance_reconciliation_workflow', 'approval_rules', 'document_engine'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'evidence_chain', 'transaction_state_machine'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['workflow', 'review', 'document_engine', 'audit_chain'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'file_hasher', 'version_diff', 'audit_chain', 'search'], 'gap': False}, {'capability_id': 'contract_clause_grounding', 'block_ids': ['knowledge', 'vector_search', 'evidence_or_refuse', 'evidence_verifier'], 'gap': False}, {'capability_id': 'performance_security_tracking', 'block_ids': ['workflow', 'notification', 'audit_chain'], 'gap': False}, {'capability_id': 'compliance_dashboard', 'block_ids': ['dashboard', 'analytics', 'notification'], 'gap': False}], 'agent_reviews': [{'capability_id': 'progress_claim_processing', 'block_ids': ['boq_processor', 'finance_canonical_model', 'finance_reconciliation_workflow', 'approval_rules', 'document_engine'], 'verdict': 'endorse', 'reason': 'BOQ parsing, governed financial model/reconciliation, named-reviewer approval, and document parsing plausibly serve progress claim preparation.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'evidence_chain', 'transaction_state_machine'], 'verdict': 'endorse', 'reason': 'CPM schedule analysis, formula execution, evidence chain, and state machine directly support delay/damages tracking.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['workflow', 'review', 'document_engine', 'audit_chain'], 'verdict': 'mismatch', 'reason': 'review block only exposes approve/reject/hide and document_engine is generic parsing; no ITP record structure, checklist, or inspection-holdpoint logic.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'file_hasher', 'version_diff', 'audit_chain', 'search'], 'verdict': 'mismatch', 'reason': 'version_diff diffs finding sets not document versions, and search is web DuckDuckGo/Serper — not a register index for project documents.'}, {'capability_id': 'contract_clause_grounding', 'block_ids': ['knowledge', 'vector_search', 'evidence_or_refuse', 'evidence_verifier'], 'verdict': 'endorse', 'reason': 'RAG knowledge, vector search, evidence-or-refuse gate, and tamper-evident verifier fit grounded clause citation well.'}, {'capability_id': 'performance_security_tracking', 'block_ids': ['workflow', 'notification', 'audit_chain'], 'verdict': 'mismatch', 'reason': 'Blocks only orchestrate, notify, and audit — no performance measurement or security posture tracking logic.'}, {'capability_id': 'compliance_dashboard', 'block_ids': ['dashboard', 'analytics', 'notification'], 'verdict': 'endorse', 'reason': 'Dashboard widgets, analytics metrics, and notification all plausibly serve a compliance dashboard surface.'}], 'agent_model': 'deepseek-chat'}


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
