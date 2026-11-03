"""Capability manifest and the kernel job roster the platform publishes."""

from __future__ import annotations

from typing import Any, Dict, List

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "progress_claims",
        "entity": "progress_claims",
        "title": "Interim payment certificates",
        "summary": "Prepares and certifies IPCs against the BOQ with Clause 14.3 retention and 50/50 release.",
        "blocks": ["finance_reconciliation", "finance_reconciliation_workflow", "validation", "document_engine", "workflow"],
        "placeholder": "PROJECT_ACCOUNTING_LEDGER_CREDENTIALS",
    },
    {
        "id": "delay_damages_tracking",
        "entity": "delay_damages_tracking",
        "title": "Delay damages",
        "summary": "Clause 8.2 Time for Completion and Clause 8.7 delay damages with the 10% cap.",
        "blocks": ["cpm_engine", "formula_executor", "analytics", "dashboard"],
        "placeholder": "PRIMAVERA_P6_SCHEDULE_CREDENTIALS",
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA / ITP records",
        "summary": "Inspection lots, hold and witness points and test results per BOQ item.",
        "blocks": ["construction_advisor", "evidence_chain", "validation", "workflow"],
        "placeholder": "PROJECT_EDMS_CREDENTIALS",
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "summary": "Controlled register with revision, provenance, checksum and retrieval.",
        "blocks": ["document_engine", "version_diff", "ingestion_provenance", "search", "storage"],
        "placeholder": "",
    },
    {
        "id": "performance_security_tracking",
        "entity": "performance_security_tracking",
        "title": "Performance security",
        "summary": "Clause 4.2 security at 10% of the Accepted Contract Amount with expiry alerts.",
        "blocks": ["workflow", "notification", "dashboard"],
        "placeholder": "BANK_GUARANTEE_AND_SURETY_PROVIDER_CREDENTIALS",
    },
    {
        "id": "defects_notification_period",
        "entity": "defects_notification_period",
        "title": "Defects notification period",
        "summary": "Clause 11.1 365-day DNP, defect notifications and close-out evidence.",
        "blocks": ["estate_maintenance", "workflow", "notification", "audit"],
        "placeholder": "DEFECTS_AND_MAINTENANCE_SYSTEM_CREDENTIALS",
    },
    {
        "id": "claim_evidence_and_approvals",
        "entity": "claim_evidence_and_approvals",
        "title": "Claim evidence and approvals",
        "summary": "Evidence classification, verification, approval routing and segregation of duties.",
        "blocks": ["evidence_classifier", "evidence_verifier", "evidence_or_refuse",
                   "approval_rules", "governance_gate", "audit_chain"],
        "placeholder": "",
    },
]

KERNEL_JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author the capability handlers, routes and schema from the brief.",
        "agent": "writer",
        "http_routes": ["/v1/capabilities", "/v1/jobs"],
    },
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store and bind verified blocks into the platform.",
        "agent": "collector",
        "http_routes": ["/v1/catalog", "/v1/provenance"],
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Stock each verified block at its locked vendor path.",
        "agent": "cloner",
        "http_routes": ["/v1/inventory"],
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the gates and report every failing capability.",
        "agent": "tester",
        "http_routes": ["/v1/gates"],
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Register the product and its provenance with the Store.",
        "agent": "store_manager",
        "http_routes": ["/v1/provenance"],
    },
]
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['analytics', 'approval_rules', 'audit', 'audit_chain', 'construction_advisor', 'cpm_engine', 'dashboard', 'document_engine', 'estate_maintenance', 'evidence_chain', 'evidence_classifier', 'evidence_or_refuse', 'evidence_verifier', 'finance_reconciliation', 'finance_reconciliation_workflow', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'notification', 'search', 'storage', 'validation', 'version_diff', 'workflow'], 'gaps': [], 'bindings': [{'capability_id': 'progress_claims', 'block_ids': ['finance_reconciliation', 'finance_reconciliation_workflow', 'validation', 'document_engine', 'workflow'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'analytics', 'dashboard'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['construction_advisor', 'evidence_chain', 'validation', 'workflow'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version_diff', 'ingestion_provenance', 'search', 'storage'], 'gap': False}, {'capability_id': 'performance_security_tracking', 'block_ids': ['workflow', 'notification', 'dashboard'], 'gap': False}, {'capability_id': 'defects_notification_period', 'block_ids': ['estate_maintenance', 'workflow', 'notification', 'audit'], 'gap': False}, {'capability_id': 'claim_evidence_and_approvals', 'block_ids': ['evidence_classifier', 'evidence_verifier', 'evidence_or_refuse', 'approval_rules', 'governance_gate', 'audit_chain'], 'gap': False}], 'agent_reviews': [], 'agent_model': ''}


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
