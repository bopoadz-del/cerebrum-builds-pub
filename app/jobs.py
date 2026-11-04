"""Kernel job roster and platform registers the operator console reads."""

from __future__ import annotations

from typing import Any, Dict, List

from app.actions import (
    claims_analytics_dashboard,
    contract_clause_governance,
    delay_damages_tracking,
    document_register,
    payment_security_and_retention_ledger,
    progress_claims,
    qa_itp_records,
)
from app.dispatch import BLOCK_IDS
from app.models import CAPABILITY_ORDER, MODELS

ACTION_MODULES = {
    module.CAPABILITY_ID: module
    for module in (
        document_register,
        progress_claims,
        delay_damages_tracking,
        qa_itp_records,
        contract_clause_governance,
        payment_security_and_retention_ledger,
        claims_analytics_dashboard,
    )
}


def _blocks_of(capability_id: str) -> List[str]:
    module = ACTION_MODULES.get(capability_id)
    return list(getattr(module, "BLOCK_IDS", []) or [])


CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": capability_id,
        "title": capability_id.replace("_", " ").capitalize(),
        "entity": MODELS[capability_id].ENTITY,
        "fields": list(MODELS[capability_id].FIELDS),
        "blocks": _blocks_of(capability_id),
    }
    for capability_id in CAPABILITY_ORDER
]

JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "agent": "consult",
        "mandate": (
            "emit the intake blueprint, resolve each capability's declared "
            "block ids into harvestable contracts, and name every capability "
            "with no block as an explicit gap"
        ),
        "http_routes": ["GET /v1/catalog", "GET /v1/capabilities"],
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "agent": "cloner",
        "mandate": (
            "vendor each resolved block's source at its pinned commit, plus "
            "the kit packs the Factory shelf assigns, and record the lock"
        ),
        "http_routes": ["GET /v1/inventory"],
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "agent": "writer",
        "mandate": "author the capability handlers, routes, surfaces and UI",
        "http_routes": ["GET /v1/capabilities"],
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "agent": "tester",
        "mandate": "run the gates and report measured verdicts, never presence",
        "http_routes": ["GET /v1/gates"],
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "agent": "store_manager",
        "mandate": "record provenance and the authority ladder this build honours",
        "http_routes": ["GET /v1/provenance"],
    },
]

INVENTORY = {
    "kernel": "CLONER",
    "locked_blocks": list(BLOCK_IDS),
    "lock": "blocks.lock.json",
    "runtime": "python3.11",
}

CATALOG = {
    "kernel": "COLLECTOR",
    "blocks": list(BLOCK_IDS),
    "capabilities": [item["id"] for item in CAPABILITIES],
}

GATES = {
    "kernel": "TESTER",
    "runs_over_http": False,
    "gates": ["writer_behaviour", "product", "store"],
}

PROVENANCE = {
    "kernel": "STORE_MANAGER",
    "precedence": "precedence.v1",
    "layers": ["certified", "documents", "formulas", "procedures"],
    "product": "Harbourline Civil Works Contracts Administration",
    "source_of_record": [
        "document:402ecf72034f4692898b07cd2079bed2_harbourline_boq.xlsx",
        "document:a2e79e3d662b42f1b56d5faafd651ffe_harbourline_contract.pdf",
    ],
}
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['document_engine', 'version', 'version_diff', 'storage', 'audit_chain', 'boq_processor', 'formula_executor', 'finance_reconciliation', 'approval_rules', 'pdf', 'cpm_engine', 'finance_planning', 'audit', 'evidence_chain', 'validation', 'workflow', 'knowledge', 'regulatory_chunker', 'evidence_or_refuse', 'governance_gate', 'finance_canonical_model', 'transaction_state_machine', 'dashboard', 'analytics', 'portfolio_rollup'], 'gaps': [], 'bindings': [{'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'version_diff', 'storage', 'audit_chain'], 'gap': False}, {'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'formula_executor', 'finance_reconciliation', 'approval_rules', 'pdf'], 'gap': False}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'finance_planning', 'audit'], 'gap': False}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'evidence_chain', 'validation', 'workflow'], 'gap': False}, {'capability_id': 'contract_clause_governance', 'block_ids': ['knowledge', 'regulatory_chunker', 'evidence_or_refuse', 'governance_gate'], 'gap': False}, {'capability_id': 'payment_security_and_retention_ledger', 'block_ids': ['finance_canonical_model', 'transaction_state_machine', 'audit_chain'], 'gap': False}, {'capability_id': 'claims_analytics_dashboard', 'block_ids': ['dashboard', 'analytics', 'portfolio_rollup'], 'gap': False}], 'agent_reviews': [{'capability_id': 'document_register', 'block_ids': ['document_engine', 'version', 'version_diff', 'storage', 'audit_chain'], 'verdict': 'endorse', 'reason': 'Document intelligence pipeline plus versioning, diffing, storage and tamper-evident audit chain plausibly serve a dual-registered document register.'}, {'capability_id': 'progress_claims', 'block_ids': ['boq_processor', 'formula_executor', 'finance_reconciliation', 'approval_rules', 'pdf'], 'verdict': 'endorse', 'reason': 'BOQ parsing, sandboxed construction formulas, decimal-safe reconciliation, named-reviewer approval ledger and PDF ingestion cover progress claims adjudication end to end.'}, {'capability_id': 'delay_damages_tracking', 'block_ids': ['cpm_engine', 'formula_executor', 'finance_planning', 'audit'], 'verdict': 'endorse', 'reason': 'CPM schedule computation with P6 XER parsing, formula execution, budget/allocation planning and audited trail map onto delay and damages tracking.'}, {'capability_id': 'qa_itp_records', 'block_ids': ['document_engine', 'evidence_chain', 'validation', 'workflow'], 'verdict': 'endorse', 'reason': 'Document parsing, SHA-256 evidence chain, validation pipeline and schedulable workflow support inspection/test plan recordkeeping; evidence_chain being in-process is a deploy note, not a binding mismatch.'}, {'capability_id': 'contract_clause_governance', 'block_ids': ['knowledge', 'regulatory_chunker', 'evidence_or_refuse', 'governance_gate'], 'verdict': 'endorse', 'reason': 'RAG knowledge, regulatory-aware chunking, evidence-or-refuse gate and fail-closed governance approval align with contract clause governance.'}, {'capability_id': 'payment_security_and_retention_ledger', 'block_ids': ['finance_canonical_model', 'transaction_state_machine', 'audit_chain'], 'verdict': 'mismatch', 'reason': 'Retention ledger needs records-retention lifecycle and security controls; canonical finance model, generic transaction state machine and audit chain cover payment state and evidence but no retention/erasure policy or security enforcement contract is present.'}, {'capability_id': 'claims_analytics_dashboard', 'block_ids': ['dashboard', 'analytics', 'portfolio_rollup'], 'verdict': 'mismatch', 'reason': 'portfolio_rollup contract aggregates property records ({id, value, status}), not claims; dashboard/analytics fit, but the rollup aggregation is a strained property-domain fit an engineer would flag.'}], 'agent_model': 'deepseek-chat'}


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
