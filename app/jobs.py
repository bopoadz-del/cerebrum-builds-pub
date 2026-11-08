"""The platform's capability roster and the kernel job descriptions.

These are the product's own data: which capabilities the platform runs, which
blocks each binds, and the five kernel roles the operator can inspect. The
routes publish them; nothing here decides a domain outcome.
"""

from __future__ import annotations

from typing import Any, Dict, List

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "progress_claim_management",
        "entity": "progress_claim_management",
        "title": "Progress claim management",
        "blocks": ["boq_processor", "finance_reconciliation_workflow", "approval_rules", "audit"],
        "summary": "Interim Payment Certificates measured against BOQ lines, with Clause 14.3 retention, Clause 4.2 performance security, approval routing and a reconciliation run.",
    },
    {
        "id": "delay_damages_tracking",
        "entity": "delay_damages_tracking",
        "title": "Delay damages tracking",
        "blocks": ["formula_executor", "notification", "audit"],
        "summary": "Elapsed time against the Time for Completion (Clause 8.2) and delay damages at a daily percentage capped at a percentage of the Accepted Contract Amount (Clause 8.7).",
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA/ITP records",
        "blocks": ["document_engine", "task_listing", "evidence_chain", "audit_chain"],
        "summary": "Inspection and test plan records tied to BOQ items: inspection lots, hold and witness points, test results, sign-offs and defect close-out through Clause 11.1.",
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "blocks": ["document_engine", "version_diff", "review", "search"],
        "summary": "A controlled register of contract, BOQ, drawing, ITP, claim and certificate documents with revision control, checksums, provenance and review status.",
    },
    {
        "id": "contract_terms_governance",
        "entity": "contract_terms_governance",
        "title": "Contract terms governance",
        "blocks": ["governance_gate", "validation"],
        "summary": "A clause register of time for completion, delay damages, retention, performance security and defects notification, with a governance gate and validation before a term is relied on.",
    },
    {
        "id": "commercial_dashboard",
        "entity": "commercial_dashboard",
        "title": "Commercial dashboard",
        "blocks": ["dashboard", "analytics", "portfolio_rollup"],
        "summary": "Claims by status, certified totals, retention held, delay exposure and outstanding inspection items in one operator surface.",
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
        "http_routes": [
            "GET /v1/capabilities",
            "POST /v1/{capability}",
            "GET /v1/{capability}",
            "GET /v1/{capability}/{id}",
        ],
        "agent": "manufacture",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the code-phase suite against what the WRITER produced and bounce failures for another writer pass.",
        "http_routes": ["GET /v1/gates"],
        "agent": "none",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Keep the store's books: register what this platform cloned and at which commit.",
        "http_routes": ["GET /v1/provenance"],
        "agent": "none",
    },
]

JOBS = KERNEL_JOBS
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['boq_processor', 'finance_reconciliation_workflow', 'approval_rules', 'audit', 'formula_executor', 'notification', 'document_engine', 'task_listing', 'evidence_chain', 'audit_chain', 'version_diff', 'review', 'search', 'governance_gate', 'validation', 'dashboard', 'analytics', 'portfolio_rollup'], 'gaps': [], 'bindings': [{'capability_id': 'progress_claim_management', 'block_ids': ['boq_processor', 'finance_reconciliation_workflow', 'approval_rules', 'audit'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'notification', 'audit'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'task_listing', 'evidence_chain', 'audit_chain'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version_diff', 'review', 'search'], 'gap': False}, {'capability_id': 'contract_terms_governance', 'block_ids': ['governance_gate', 'validation'], 'gap': False}, {'capability_id': 'commercial_dashboard', 'block_ids': ['dashboard', 'analytics', 'portfolio_rollup'], 'gap': False}], 'agent_reviews': [{'capability_id': 'progress_claim_management', 'block_ids': ['boq_processor', 'finance_reconciliation_workflow', 'approval_rules', 'audit'], 'verdict': 'endorse', 'reason': 'BOQ parsing plus actuals-vs-budget reconciliation, named-reviewer approval ledger, and tamper-evident audit all plausibly serve progress claims.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'notification', 'audit'], 'verdict': 'mismatch', 'reason': 'Formula sandbox, notification, and audit give no delay event, notice, or time-bar/liquidated-damages logic; core tracking is unbound.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'task_listing', 'evidence_chain', 'audit_chain'], 'verdict': 'mismatch', 'reason': 'task_listing is a geo task-marketplace listing block, irrelevant to inspection/test-plan records; two duplicate evidence chains also strain the fit.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version_diff', 'review', 'search'], 'verdict': 'mismatch', 'reason': 'version_diff diffs finding sets, not document revisions, and web search is not register logic; only document parsing is a plausible fit.'}, {'capability_id': 'contract_terms_governance', 'block_ids': ['governance_gate', 'validation'], 'verdict': 'endorse', 'reason': 'Fail-closed named approval gate plus validation pipeline can plausibly govern contract-terms changes.'}, {'capability_id': 'commercial_dashboard', 'block_ids': ['dashboard', 'analytics', 'portfolio_rollup'], 'verdict': 'mismatch', 'reason': 'portfolio_rollup aggregates property records {id,value,status}, a strained sit for contract commercial rollups; dashboard and analytics carry the fit.'}], 'agent_model': 'deepseek-chat'}


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
