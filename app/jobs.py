"""The platform's capability roster and the kernel job descriptions.

These are the product's own data: which capabilities the platform runs, which
blocks each binds, and the five kernel roles the operator can inspect. The
routes publish them; nothing here decides a domain outcome.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "contract_source_of_record",
        "entity": "contract_source_of_record",
        "title": "Contract source of record",
        "blocks": ["document_engine", "ocr", "pdf", "storage", "knowledge", "ingestion_provenance"],
        "summary": "Hold the uploaded contract excerpt and BOQ as the single source of record; cite document:<filename> for every clause and BOQ line.",
    },
    {
        "id": "progress_claims",
        "entity": "progress_claims",
        "title": "Progress claims",
        "blocks": [
            "finance_reconciliation",
            "finance_canonical_model",
            "boq_processor",
            "validation",
            "approval_rules",
            "transaction_state_machine",
            "audit",
        ],
        "summary": "Administers Interim Payment Certificates: BOQ valuation, 5% retention under Clause 14.3, performance-security deduction under Clause 4.2, and the 50/50 release points.",
    },
    {
        "id": "time_and_delay_damages",
        "entity": "time_and_delay_damages",
        "title": "Time and delay damages",
        "blocks": ["cpm_engine", "formula_executor", "finance_planning", "notification", "dashboard", "audit"],
        "summary": "Tracks Time for Completion (730 days, Clause 8.2) and delay-damages exposure at 0.1%/day capped at 10% of the Accepted Contract Amount (Clause 8.7).",
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA/ITP records",
        "blocks": ["workbench", "workflow", "capture", "evidence_chain", "review", "audit_chain"],
        "summary": "Inspection and test plans tied to BOQ items: inspection lots, hold and witness points, and a pass/fail result per lot.",
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "blocks": ["document_engine", "version", "version_diff", "search", "file_hasher", "audit"],
        "summary": "Controlled register of contract, BOQ, drawing, report and certificate documents with revision, checksum and provenance.",
    },
    {
        "id": "role_based_access_and_audit",
        "entity": "role_based_access_and_audit",
        "title": "Role-based access and audit",
        "blocks": ["auth", "multi_tenant_rbac", "audit_fail_closed", "governance_gate"],
        "summary": "Role/permission decisions for contract administration, recorded in the fail-closed audit ledger.",
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

JOBS = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": KERNEL_JOBS[0]["mandate"],
        "agent": "collector",
        "http_routes": ["GET /v1/catalog"],
        "gate": "every referenced block id is dual-registered; gaps enumerated",
        "read_only": True,
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": KERNEL_JOBS[1]["mandate"],
        "agent": "none",
        "http_routes": ["GET /v1/inventory"],
        "gate": "every vendored block imports with no network configured",
        "read_only": False,
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": KERNEL_JOBS[2]["mandate"],
        "agent": "manufacture",
        "http_routes": KERNEL_JOBS[2]["http_routes"],
        "gate": "workspace imports and type-checks clean",
        "read_only": False,
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": KERNEL_JOBS[3]["mandate"],
        "agent": "none",
        "http_routes": ["GET /v1/gates"],
        "gate": "code-phase suite green (pytest -m 'not pilot')",
        "read_only": False,
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": KERNEL_JOBS[4]["mandate"],
        "agent": "none",
        "http_routes": ["GET /v1/provenance"],
        "gate": "store_manager.assert_store_op_allowed passes for every op applied",
        "read_only": False,
    },
]

GATES = {
    "kernel": "TESTER",
    "title": "Acceptance inspector",
    "mandate": KERNEL_JOBS[3]["mandate"],
    "agent": "none",
    "runs_over_http": False,
    "suite": [
        {"file": "tests/test_smoke.py", "covers": "import, offline dispatch load, handle() returns a mapping", "gated": True},
        {"file": "tests/test_smoke.py", "covers": "Store-backed handle() ok and nested error scan", "marker": "pilot", "gated": False},
        {"file": "tests/test_data_lifecycle.py", "covers": "Alembic up/down, restore drill, parallel writes", "gated": True},
        {"file": "tests/test_deploy.py", "covers": "Fail-closed /health, correlation logs, revision rollback identity", "gated": True},
        {"file": "tests/test_domain_acceptance.py", "covers": "Ten business outcomes through execute_action", "marker": "pilot", "gated": False},
        {"file": "tests/test_routes.py", "covers": "HTTP 200 JSON for /health, kernel jobs, and each capability POST", "gated": True},
        {"file": "tests/test_routes.py", "covers": "Store-backed POST accepted and persisted", "marker": "pilot", "gated": False},
    ],
}


def _read_workspace_json(relative: str) -> Optional[Dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / relative
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _job(kernel: str) -> Dict[str, Any]:
    for item in JOBS:
        if item["kernel"] == kernel:
            return dict(item)
    return {"kernel": kernel}


def inventory() -> Dict[str, Any]:
    payload = _job("CLONER")
    payload["lock"] = _read_workspace_json("blocks.lock.json") or {
        "schema": "blocks.lock.v1",
        "blocks": {},
    }
    return payload


def provenance() -> Dict[str, Any]:
    payload = _job("STORE_MANAGER")
    payload["build"] = _read_workspace_json("docs/provenance/provenance.json") or {}
    lock = _read_workspace_json("blocks.lock.json") or {}
    payload["clones"] = lock.get("blocks") or {}
    payload["store_ops"] = []
    return payload
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['document_engine', 'ocr', 'pdf', 'storage', 'knowledge', 'ingestion_provenance', 'finance_reconciliation', 'finance_canonical_model', 'boq_processor', 'validation', 'approval_rules', 'transaction_state_machine', 'audit', 'cpm_engine', 'formula_executor', 'finance_planning', 'notification', 'dashboard', 'workbench', 'workflow', 'capture', 'evidence_chain', 'review', 'audit_chain', 'version', 'version_diff', 'search', 'file_hasher', 'auth', 'multi_tenant_rbac', 'audit_fail_closed', 'governance_gate'], 'gaps': [], 'bindings': [{'capability_id': 'contract_source_of_record', 'block_ids': ['document_engine', 'ocr', 'pdf', 'storage', 'knowledge', 'ingestion_provenance'], 'gap': False}, {'capability_id': 'progress_claims', 'block_ids': ['finance_reconciliation', 'finance_canonical_model', 'boq_processor', 'validation', 'approval_rules', 'transaction_state_machine', 'audit'], 'gap': False}, {'capability_id': 'time_and_delay_damages', 'block_ids': ['cpm_engine', 'formula_executor', 'finance_planning', 'notification', 'dashboard', 'audit'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['workbench', 'workflow', 'capture', 'evidence_chain', 'review', 'audit_chain'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'version_diff', 'search', 'file_hasher', 'audit'], 'gap': False}, {'capability_id': 'role_based_access_and_audit', 'block_ids': ['auth', 'multi_tenant_rbac', 'audit_fail_closed', 'governance_gate'], 'gap': False}], 'agent_reviews': [{'capability_id': 'contract_source_of_record', 'block_ids': ['document_engine', 'ocr', 'pdf', 'storage', 'knowledge', 'ingestion_provenance'], 'verdict': 'endorse', 'reason': 'Parse/OCR/PDF extraction plus storage, RAG query and provenance labeling fit a contract source-of-record intake.'}, {'capability_id': 'progress_claims', 'block_ids': ['finance_reconciliation', 'finance_canonical_model', 'boq_processor', 'validation', 'approval_rules', 'transaction_state_machine', 'audit'], 'verdict': 'endorse', 'reason': 'BOQ quantities, decimal-safe reconciliation, approval ledger and audited state machine suit progress claim assessment.'}, {'capability_id': 'time_and_delay_damages', 'block_ids': ['cpm_engine', 'formula_executor', 'finance_planning', 'notification', 'dashboard', 'audit'], 'verdict': 'endorse', 'reason': 'CPM float/critical path, formula execution, budget planning and dashboards directly support delay and damages analysis.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['workbench', 'workflow', 'capture', 'evidence_chain', 'review', 'audit_chain'], 'verdict': 'mismatch', 'reason': 'QA/ITP inspection records need capture, evidence chain and review, but the bounded coding-agent workbench binding is a strained fit for site QA records.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'version_diff', 'search', 'file_hasher', 'audit'], 'verdict': 'endorse', 'reason': 'Document parsing, versioning, hashing and audit form a plausible register; search is a loose but minor fit.'}, {'capability_id': 'role_based_access_and_audit', 'block_ids': ['auth', 'multi_tenant_rbac', 'audit_fail_closed', 'governance_gate'], 'verdict': 'endorse', 'reason': 'Fail-closed auth, tenant RBAC, audit middleware and governance gate align with access control and audit capability.'}], 'agent_model': 'deepseek-chat'}


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
