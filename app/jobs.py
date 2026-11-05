"""The capability roster and the kernel job roster the console reads.

One declaration of what this platform can do, so the routes, the kernel
S12 specs and the console all read the same list.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import models

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "progress_claims",
        "entity": "progress_claims",
        "title": "Interim Payment Certificates",
        "summary": (
            "Certify progress claims against priced BOQ measured quantities, "
            "holding retention under clause 14.3 and the performance security "
            "under clause 4.2."
        ),
        "sources": [
            "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx",
            "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
        ],
        "blocks": [
            "boq_processor",
            "finance_reconciliation",
            "finance_reconciliation_workflow",
            "approval_rules",
            "pdf",
        ],
    },
    {
        "id": "delay_damages_tracking",
        "entity": "delay_damages_tracking",
        "title": "Delay damages",
        "summary": (
            "Track Time for Completion (clause 8.2, 730 days) and compute delay "
            "damages at 0.1% of the Accepted Contract Amount per day, capped at "
            "10% (clause 8.7)."
        ),
        "sources": [
            "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"
        ],
        "blocks": ["formula_executor", "cpm_engine", "validation"],
    },
    {
        "id": "qa_itp_records",
        "entity": "qa_itp_records",
        "title": "QA / ITP records",
        "summary": (
            "Capture inspection and test plan records, hold points and signed-off "
            "ITP sheets as evidence tied to the BOQ works."
        ),
        "sources": [
            "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx"
        ],
        "blocks": ["document_engine", "evidence_chain", "audit"],
    },
    {
        "id": "document_register",
        "entity": "document_register",
        "title": "Document register",
        "summary": (
            "A controlled register of the contract, BOQ, drawings and "
            "correspondence with revision, checksum and provenance."
        ),
        "sources": [
            "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
            "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx",
        ],
        "blocks": ["document_engine", "file_hasher", "ingestion_provenance", "version"],
    },
    {
        "id": "retention_defects_release",
        "entity": "retention_defects_release",
        "title": "Retention and defects release",
        "summary": (
            "Schedule the 50% retention release at Taking-Over and the remaining "
            "50% at the end of the 365-day Defects Notification Period, and hold "
            "the performance security obligation."
        ),
        "sources": [
            "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf"
        ],
        "blocks": ["finance_planning", "transaction_state_machine", "notification"],
    },
    {
        "id": "contract_verification_gate",
        "entity": "contract_verification_gate",
        "title": "Contract verification gate",
        "summary": (
            "Refuse or flag any claim, certificate or record that cannot be "
            "grounded in a governing clause or a priced BOQ item."
        ),
        "sources": [
            "document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf",
            "document:d11a8fb09f114c4fb978033045b976c7_harbourline_boq.xlsx",
        ],
        "blocks": ["evidence_or_refuse", "governance_gate", "audit_chain"],
    },
]

CAPABILITY_IDS = [row["id"] for row in CAPABILITIES]

ROUTE_ENTITIES: Dict[str, str] = {row["id"]: row["entity"] for row in CAPABILITIES}

KERNEL_JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Pin every locked block to one path and refuse a missing one at start-up.",
        "http_routes": ["/v1/inventory"],
        "agent": "factory-cloner",
    },
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey what the Store already provides before a line is written.",
        "http_routes": ["/v1/catalog"],
        "agent": "factory-collector",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author the capabilities, their persistence and their console.",
        "http_routes": ["/v1/capabilities"],
        "agent": "factory-writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Score the booted product against the acceptance floor.",
        "http_routes": ["/v1/gates"],
        "agent": "factory-tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Register the built platform and its provenance with the Store.",
        "http_routes": ["/v1/provenance"],
        "agent": "factory-store-manager",
    },
]


def capability(capability_id: str) -> Dict[str, Any] | None:
    for row in CAPABILITIES:
        if row["id"] == capability_id:
            return row
    return None


def fields_for(capability_id: str) -> List[Dict[str, Any]]:
    model = models.model_for(capability_id)
    if model is None:
        return []
    out = []
    for name in model.FIELDS:
        rules = dict(model.CONSTRAINTS.get(name) or {})
        out.append(
            {
                "name": name,
                "type": rules.get("type", "str"),
                "required": bool(rules.get("required")),
                "allowed_values": list(rules.get("allowed_values") or []),
                "min": rules.get("min"),
                "max": rules.get("max"),
            }
        )
    return out
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['boq_processor', 'finance_reconciliation', 'finance_reconciliation_workflow', 'approval_rules', 'pdf', 'formula_executor', 'cpm_engine', 'validation', 'document_engine', 'evidence_chain', 'audit', 'file_hasher', 'ingestion_provenance', 'version', 'finance_planning', 'transaction_state_machine', 'notification', 'evidence_or_refuse', 'governance_gate', 'audit_chain'], 'gaps': [], 'bindings': [{'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'finance_reconciliation', 'finance_reconciliation_workflow', 'approval_rules', 'pdf'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'cpm_engine', 'validation'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'evidence_chain', 'audit'], 'gap': False}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'file_hasher', 'ingestion_provenance', 'version'], 'gap': False}, {'capability_id': 'retention_defects_release', 'block_ids': ['finance_planning', 'transaction_state_machine', 'notification'], 'gap': False}, {'capability_id': 'contract_verification_gate', 'block_ids': ['evidence_or_refuse', 'governance_gate', 'audit_chain'], 'gap': False}], 'agent_reviews': [{'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'finance_reconciliation', 'finance_reconciliation_workflow', 'approval_rules', 'pdf'], 'verdict': 'endorse', 'reason': 'BOQ parsing plus decimal reconciliation of claimed vs certified quantities, approval ledger and PDF claim extraction fit progress-claim assessment.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['formula_executor', 'cpm_engine', 'validation'], 'verdict': 'endorse', 'reason': 'CPM engine with float/critical path and formula executor for delay-day costing directly serve delay and damages tracking.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'evidence_chain', 'audit'], 'verdict': 'endorse', 'reason': 'Document parsing for ITP records with tamper-evident evidence chain and audit trail matches QA inspection record keeping.'}, {'capability_id': 'document_register', 'block_ids': ['document_engine', 'file_hasher', 'ingestion_provenance', 'version'], 'verdict': 'endorse', 'reason': 'Hashing, provenance labels and version control for parsed documents form a coherent controlled document register.'}, {'capability_id': 'retention_defects_release', 'block_ids': ['finance_planning', 'transaction_state_machine', 'notification'], 'verdict': 'mismatch', 'reason': 'Budget/allocation planning and marketplace transaction lifecycle are strained fits for defects retention and release; gap for defect lifecycle logic.'}, {'capability_id': 'contract_verification_gate', 'block_ids': ['evidence_or_refuse', 'governance_gate', 'audit_chain'], 'verdict': 'endorse', 'reason': 'Evidence-or-refuse judgement, fail-closed approval gate and tamper-evident chain plausibly enforce contract verification.'}], 'agent_model': 'deepseek-chat'}


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
