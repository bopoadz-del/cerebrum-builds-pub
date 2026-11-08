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
        "id": "contract_and_boq_source_of_record",
        "entity": "contract_and_boq_source_of_record",
        "title": "Contract and BOQ source of record",
        "blocks": ["document_engine", "pdf", "validation", "audit_chain"],
        "summary": "Hold the uploaded contract excerpt and BOQ as the immutable source of record: resolved clauses, BOQ quantities and rates, and a citation to the document each term came from.",
    },
    {
        "id": "progress_claims_and_payment_certificates",
        "entity": "progress_claims_and_payment_certificates",
        "title": "Progress claims and payment certificates",
        "blocks": ["boq_processor", "approval_rules", "workflow", "finance_canonical_model", "billing", "audit"],
        "summary": "Interim Payment Certificates measured against BOQ lines, with Clause 14.3 retention, Clause 4.2 performance security, approval routing and carried-forward certified quantities.",
    },
    {
        "id": "delay_damages_tracking",
        "entity": "delay_damages_tracking",
        "title": "Delay damages tracking",
        "blocks": ["cpm_engine", "formula_executor", "transaction_state_machine", "notification", "evidence_chain"],
        "summary": "Elapsed time against the 730-day Time for Completion (Clause 8.2) and delay damages at 0.1% per day capped at 10% (Clause 8.7), with capped exposure flagged and evidence chained.",
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA/ITP records",
        "blocks": ["capture", "evidence_classifier", "evidence_verifier", "file_hasher"],
        "summary": "Inspection and test plan records tied to BOQ items: inspection lots, hold and witness points, test results, sign-offs and defect close-out through Clause 11.1.",
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "blocks": ["document_engine", "search", "version", "audit"],
        "summary": "A controlled register of contract, BOQ, drawing, ITP, claim and certificate documents with revision control, checksums, provenance and search.",
    },
    {
        "id": "claim_review_and_dispute_resolution",
        "entity": "claim_review_and_dispute_resolution",
        "title": "Claim review and dispute resolution",
        "blocks": ["review", "dispute_resolution", "evidence_or_refuse", "audit_chain"],
        "summary": "Reviews submitted claims against the contract and BOQ source of record, records determinations on measured quantities or clause interpretation, and keeps the evidence trail.",
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


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['document_engine', 'pdf', 'validation', 'audit_chain', 'boq_processor', 'approval_rules', 'workflow', 'finance_canonical_model', 'billing', 'audit', 'cpm_engine', 'formula_executor', 'transaction_state_machine', 'notification', 'evidence_chain', 'capture', 'evidence_classifier', 'evidence_verifier', 'file_hasher', 'search', 'version', 'review', 'dispute_resolution', 'evidence_or_refuse'], 'gaps': [], 'bindings': [{'capability_id': 'contract_and_boq_source_of_record', 'block_ids': ['document_engine', 'pdf', 'validation', 'audit_chain'], 'gap': False}, {'capability_id': 'progress_claims_and_payment_certificates', 'block_ids': ['boq_processor', 'approval_rules', 'workflow', 'finance_canonical_model', 'billing', 'audit'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'transaction_state_machine', 'notification', 'evidence_chain'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['capture', 'evidence_classifier', 'evidence_verifier', 'file_hasher'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'search', 'version', 'audit'], 'gap': False}, {'capability_id': 'claim_review_and_dispute_resolution', 'block_ids': ['review', 'dispute_resolution', 'evidence_or_refuse', 'audit_chain'], 'gap': False}], 'agent_reviews': [{'capability_id': 'contract_and_boq_source_of_record', 'block_ids': ['document_engine', 'pdf', 'validation', 'audit_chain'], 'verdict': 'endorse', 'reason': 'PDF extraction plus document parse/reason/map and validation pipeline plausibly support a contracts/BOQ source of record with tamper-evident audit.'}, {'capability_id': 'progress_claims_and_payment_certificates', 'block_ids': ['boq_processor', 'approval_rules', 'workflow', 'finance_canonical_model', 'billing', 'audit'], 'verdict': 'mismatch', 'reason': 'Billing block is SaaS quota/subscription/invoice, not construction payment certificates; finance model is FinanceOps governance and approval_rules is clearance-rule approval — strained fit for progress-claim certification.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'transaction_state_machine', 'notification', 'evidence_chain'], 'verdict': 'endorse', 'reason': 'CPM schedule engine with float/critical path, formula execution, and evidence chain genuinely serve delay/damages analysis.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['capture', 'evidence_classifier', 'evidence_verifier', 'file_hasher'], 'verdict': 'mismatch', 'reason': 'Evidence classifier is a fire-pump/fire-life-safety commissioning classifier, not ITP/QA inspection; capture/OCR/hashing fit but classification logic is domain-mismatched.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'search', 'version', 'audit'], 'verdict': 'mismatch', 'reason': 'Search is web search (DuckDuckGo/Serper) and version is software artifact versioning — neither serves a construction document register; document_engine and audit fit.'}, {'capability_id': 'claim_review_and_dispute_resolution', 'block_ids': ['review', 'dispute_resolution', 'evidence_or_refuse', 'audit_chain'], 'verdict': 'endorse', 'reason': 'Dispute lifecycle with party-gated evidence, evidence-or-refuse judging, and tamper-evident chain plausibly serve claim review and dispute resolution.'}], 'agent_model': 'deepseek-chat'}


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
