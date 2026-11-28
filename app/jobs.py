# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['task_listing', 'vendor_catalog', 'dispatch_matching', 'transaction_state_machine', 'notification', 'payment_escrow', 'dashboard', 'dispute_resolution', 'audit', 'config', 'email', 'billing'], 'gaps': ['contractor_availability_schedule'], 'bindings': [{'capability_id': 'customer_booking_flow', 'block_ids': ['task_listing'], 'gap': False}, {'capability_id': 'contractor_onboarding_and_service_areas', 'block_ids': ['vendor_catalog'], 'gap': False}, {'capability_id': 'contractor_availability_schedule', 'block_ids': [], 'gap': True}, {'capability_id': 'location_based_matching', 'block_ids': ['dispatch_matching'], 'gap': False}, {'capability_id': 'booking_status_lifecycle', 'block_ids': ['transaction_state_machine'], 'gap': False}, {'capability_id': 'booking_notifications', 'block_ids': ['notification'], 'gap': False}, {'capability_id': 'invoicing_and_payouts', 'block_ids': ['payment_escrow'], 'gap': False}, {'capability_id': 'ops_back_office', 'block_ids': ['dashboard', 'dispute_resolution'], 'gap': False}, {'capability_id': 'audit', 'block_ids': ['audit'], 'gap': False}, {'capability_id': 'config', 'block_ids': ['config'], 'gap': False}, {'capability_id': 'email', 'block_ids': ['email'], 'gap': False}, {'capability_id': 'billing', 'block_ids': ['billing'], 'gap': False}], 'agent_reviews': [{'capability_id': 'customer_booking_flow', 'block_ids': ['task_listing'], 'verdict': 'endorse', 'reason': 'Task listing covers fail-closed creation/validation, geo qualification, and category/budget/keyword filtering — the core of a customer booking flow.'}, {'capability_id': 'contractor_onboarding_and_service_areas', 'block_ids': ['vendor_catalog'], 'verdict': 'endorse', 'reason': 'Vendor registration with service areas plus item management and availability is a direct fit for contractor onboarding and coverage.'}, {'capability_id': 'contractor_availability_schedule', 'block_ids': [], 'verdict': 'mismatch', 'reason': 'No block bound; scheduling/calendar logic is unauthored and must be written by the writer agent — flag as explicit gap.'}, {'capability_id': 'location_based_matching', 'block_ids': ['dispatch_matching'], 'verdict': 'endorse', 'reason': 'Skill/distance/load/reputation scoring with capacity-guarded assignment matches location-based matching.'}, {'capability_id': 'booking_status_lifecycle', 'block_ids': ['transaction_state_machine'], 'verdict': 'endorse', 'reason': 'Fail-closed lifecycle state machine with actor guards and audit trail directly serves booking status transitions.'}, {'capability_id': 'booking_notifications', 'block_ids': ['notification'], 'verdict': 'endorse', 'reason': 'Multi-channel send/broadcast actions cover booking notification needs.'}, {'capability_id': 'invoicing_and_payouts', 'block_ids': ['payment_escrow'], 'verdict': 'endorse', 'reason': 'Escrow hold/release/partial-release/refund with frozen Decimal fees serves payouts; invoice generation depends on the declared billing/payment_split dependency, worth noting at tender review.'}, {'capability_id': 'ops_back_office', 'block_ids': ['dashboard', 'dispute_resolution'], 'verdict': 'endorse', 'reason': 'Dashboard metrics/widgets plus party-gated dispute lifecycle with platform resolution fit a back-office ops console.'}, {'capability_id': 'audit', 'block_ids': ['audit'], 'verdict': 'endorse', 'reason': 'Log/query/export/verify-chain/tamper-check actions map one-to-one onto the audit capability.'}, {'capability_id': 'config', 'block_ids': ['config'], 'verdict': 'endorse', 'reason': 'get/get_all/set configuration actions are exactly the required surface.'}, {'capability_id': 'email', 'block_ids': ['email'], 'verdict': 'endorse', 'reason': 'send/send_template/validate_address covers transactional email delivery.'}, {'capability_id': 'billing', 'block_ids': ['billing'], 'verdict': 'endorse', 'reason': 'Usage, quota, subscription, invoice, and webhook actions match the billing capability.'}], 'agent_model': 'deepseek-flash'}


CAPABILITIES = []


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
