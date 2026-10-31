"""Kernel job roster and the capability manifest the console discovers."""

from __future__ import annotations

from typing import Any, Dict, List

JOBS: List[Dict[str, Any]] = [
    {
        "kernel": "COLLECTOR",
        "title": "Binding surveyor",
        "mandate": "Survey the Store registry and bind verified blocks to capabilities.",
        "http_routes": ["/v1/catalog", "/v1/inventory"],
        "agent": "collector",
    },
    {
        "kernel": "CLONER",
        "title": "Block stocker",
        "mandate": "Lay the verified blocks into vendor/ under the lock file.",
        "http_routes": ["/v1/inventory"],
        "agent": "cloner",
    },
    {
        "kernel": "WRITER",
        "title": "Platform manufacturer",
        "mandate": "Author routes, handlers, schema and the operator console.",
        "http_routes": ["/v1/capabilities"],
        "agent": "writer",
    },
    {
        "kernel": "TESTER",
        "title": "Acceptance inspector",
        "mandate": "Run the pilot suite and the one-record round-trip per capability.",
        "http_routes": ["/v1/gates"],
        "agent": "tester",
    },
    {
        "kernel": "STORE_MANAGER",
        "title": "Store registrar",
        "mandate": "Record provenance and publish the pilot candidate.",
        "http_routes": ["/v1/provenance"],
        "agent": "store_manager",
    },
]

CAPABILITIES: List[Dict[str, Any]] = [
    {"id": "document_grounded_qa", "entity": "document_grounded_qa",
     "blocks": ["vector_search", "search", "llm_enhancer"],
     "name": "Document grounded Q&A"},
    {"id": "supplier_cost_and_parts_pricing", "entity": "supplier_cost_and_parts_pricing",
     "blocks": ["finance_canonical_model", "finance_import", "finance_data_quality",
                "finance_reconciliation", "validation"],
     "name": "Supplier cost and parts pricing"},
    {"id": "cost_price_movement_alerts", "entity": "cost_price_movement_alerts",
     "blocks": ["approval_rules", "notification", "email", "analytics", "dashboard"],
     "name": "Cost and price movement alerts"},
    {"id": "document_revision_nudges", "entity": "document_revision_nudges",
     "blocks": ["version_diff", "microsoft_365", "notification", "email", "audit"],
     "name": "Document revision nudges"},
    {"id": "document_ingestion_from_m365_and_upload",
     "entity": "document_ingestion_from_m365_and_upload",
     "blocks": ["onedrive", "microsoft_365", "ingestion_provenance", "pdf"],
     "name": "Document ingestion"},
    {"id": "manager_dashboard", "entity": "manager_dashboard",
     "blocks": ["dashboard", "analytics", "aesthetic_kit"],
     "name": "Manager dashboard"},
    {"id": "manager_only_access", "entity": "manager_only_access",
     "blocks": ["auth", "user_auth", "multi_tenant_rbac"],
     "name": "Manager-only access"},
    {"id": "sap_odata_connector", "entity": "sap_odata_connector",
     "blocks": ["sap_odata_connector"],
     "name": "SAP OData connector"},
]

CAPABILITY_ENTITIES = {row["id"]: row["entity"] for row in CAPABILITIES}
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['knowledge', 'search', 'vector_search', 'llm_enhancer', 'ocr', 'finance_canonical_model', 'finance_import', 'finance_data_quality', 'finance_reconciliation', 'validation', 'approval_rules', 'notification', 'email', 'analytics', 'dashboard', 'version_diff', 'microsoft_365', 'audit', 'onedrive', 'capture', 'ingestion_provenance', 'pdf', 'aesthetic_kit', 'auth', 'user_auth', 'multi_tenant_rbac', 'sap_odata_connector'], 'gaps': [], 'bindings': [{'capability_id': 'document_grounded_qa', 'block_ids': ['knowledge', 'search', 'vector_search', 'llm_enhancer', 'ocr'], 'gap': False}, {'capability_id': 'supplier_cost_and_parts_pricing', 'block_ids': ['finance_canonical_model', 'finance_import', 'finance_data_quality', 'finance_reconciliation', 'validation'], 'gap': False}, {'capability_id': 'cost_price_movement_alerts', 'block_ids': ['approval_rules', 'notification', 'email', 'analytics', 'dashboard'], 'gap': False}, {'capability_id': 'document_revision_nudges', 'block_ids': ['version_diff', 'microsoft_365', 'notification', 'email', 'audit'], 'gap': False}, {'capability_id': 'document_ingestion_from_m365_and_upload', 'block_ids': ['onedrive', 'microsoft_365', 'capture', 'ingestion_provenance', 'pdf'], 'gap': False}, {'capability_id': 'manager_dashboard', 'block_ids': ['dashboard', 'analytics', 'aesthetic_kit'], 'gap': False}, {'capability_id': 'manager_only_access', 'block_ids': ['auth', 'user_auth', 'multi_tenant_rbac'], 'gap': False}, {'capability_id': 'sap_odata_connector', 'block_ids': ['sap_odata_connector'], 'gap': False}], 'agent_reviews': [{'capability_id': 'document_grounded_qa', 'block_ids': ['knowledge', 'search', 'vector_search', 'llm_enhancer', 'ocr'], 'verdict': 'endorse', 'reason': 'knowledge RAG ask/search + vector_search semantic retrieval + ocr extraction directly serve grounded QA over documents; search and llm_enhancer are supplementary but plausible.'}, {'capability_id': 'supplier_cost_and_parts_pricing', 'block_ids': ['finance_canonical_model', 'finance_import', 'finance_data_quality', 'finance_reconciliation', 'validation'], 'verdict': 'endorse', 'reason': 'Finance canonical model, import normalization, DQ controls and reconciliation support supplier cost/pricing data; validation is generic pipeline cert, acceptable.'}, {'capability_id': 'cost_price_movement_alerts', 'block_ids': ['approval_rules', 'notification', 'email', 'analytics', 'dashboard'], 'verdict': 'endorse', 'reason': 'notification/email/analytics/dashboard cover alerting and movement reporting; approval_rules is a weak fit (clearance-rule review, not cost alerts) but does not break the capability.'}, {'capability_id': 'document_revision_nudges', 'block_ids': ['version_diff', 'microsoft_365', 'notification', 'email', 'audit'], 'verdict': 'endorse', 'reason': 'version_diff detects changes, notification/email nudge, audit logs delivery, M365 provides source context; coherent for revision nudges.'}, {'capability_id': 'document_ingestion_from_m365_and_upload', 'block_ids': ['onedrive', 'microsoft_365', 'capture', 'ingestion_provenance', 'pdf'], 'verdict': 'endorse', 'reason': 'OneDrive/M365 Graph fetch, capture OCR, pdf extraction and ingestion_provenance hashing/labels map directly to ingestion from M365 and upload.'}, {'capability_id': 'manager_dashboard', 'block_ids': ['dashboard', 'analytics', 'aesthetic_kit'], 'verdict': 'endorse', 'reason': 'dashboard render/widgets + analytics metrics deliver manager view; aesthetic_kit is a presentation/reasoning add-on, acceptable though thin.'}, {'capability_id': 'manager_only_access', 'block_ids': ['auth', 'user_auth', 'multi_tenant_rbac'], 'verdict': 'endorse', 'reason': 'auth key/permission checks, user_auth tokens, and fail-closed multi_tenant_rbac directly serve manager-only access control.'}, {'capability_id': 'sap_odata_connector', 'block_ids': ['sap_odata_connector'], 'verdict': 'mismatch', 'reason': 'Capability depends on SAP OData reads (GL accounts, PO headers) but the single bound block is an honest stub with no OData implemented — it fails closed, so the capability cannot be served.'}], 'agent_model': 'deepseek-chat'}


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
