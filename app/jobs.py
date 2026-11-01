"""The kernel job roster, the binding catalog, and the read-only answers.

Written by the factory WRITER role (codewhale exec). JOBS/CATALOG/GATES are
the five kernel jobs this platform's build ran. GET /v1/jobs publishes them;
GET /v1/catalog, /v1/inventory, /v1/gates and /v1/provenance answer with the
shape each kernel owns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_TITLES = {
    "COLLECTOR": "Binding surveyor",
    "CLONER": "Block stocker",
    "WRITER": "Platform manufacturer",
    "TESTER": "Acceptance inspector",
    "STORE_MANAGER": "Store registrar",
}

_MANDATES = {
    "COLLECTOR": (
        "Emit intake_blueprint.v1: the vertical, each capability in the "
        "customer's own words with a normalized id, the roles, data sources, "
        "integrations and constraints, and the Store block ids each "
        "capability is bound to. Name every capability with no block as an "
        "explicit gap so the WRITER authors that logic. Do not invent block "
        "ids and do not mutate the plan."
    ),
    "CLONER": (
        "Vendor each resolved block's source at a pinned commit, plus the "
        "local dispatch runtime those shims stand on, plus the kit packs the "
        "Factory shelf assigns those blocks to, so handlers import blocks "
        "instead of calling the store over HTTP. Write only vendor/**, "
        "kits/** and blocks.lock.json."
    ),
    "WRITER": (
        "Manufacture the platform over the vendored stock: capability "
        "handlers, domain models, persistence, the HTTP surface including "
        "each kernel's job routes, and the operator console that drives the "
        "live routes. Do not touch tests/ or vendor/."
    ),
    "TESTER": (
        "Write and run the code-phase suite against what the WRITER produced "
        "and bounce failures back for another writer pass. Store-backed "
        "execute-all is pilot coverage, not this gate. Never patch app/. "
        "Never run the suite over HTTP -- GET /v1/gates describes coverage "
        "only."
    ),
    "STORE_MANAGER": (
        "Keep the store's books: register what this platform cloned and at "
        "which commit. Applies no store op in this minimal form."
    ),
}

_ROUTES = {
    "COLLECTOR": ["GET /v1/catalog"],
    "CLONER": ["GET /v1/inventory"],
    "WRITER": [
        "GET /v1/capabilities",
        "POST /v1/{capability}",
        "GET /v1/{capability}",
        "GET /v1/{capability}/{id}",
    ],
    "TESTER": ["GET /v1/gates"],
    "STORE_MANAGER": ["GET /v1/provenance"],
}

_AGENTS = {
    "COLLECTOR": "consult",
    "CLONER": "none",
    "WRITER": "manufacture",
    "TESTER": "none",
    "STORE_MANAGER": "none",
}

_GATES = {
    "COLLECTOR": "every referenced block id is dual-registered; gaps enumerated",
    "CLONER": "every vendored block imports with no network configured",
    "WRITER": "workspace imports and serves its own declared routes",
    "TESTER": "code-phase suite green (pytest -m 'not pilot')",
    "STORE_MANAGER": "store_manager.assert_store_op_allowed passes for every op applied",
}

JOBS = [
    {
        "kernel": kernel,
        "title": _TITLES[kernel],
        "mandate": _MANDATES[kernel],
        "agent": _AGENTS[kernel],
        "http_routes": list(_ROUTES[kernel]),
        "gate": _GATES[kernel],
        "read_only": kernel in ("COLLECTOR", "TESTER"),
    }
    for kernel in ("COLLECTOR", "CLONER", "WRITER", "TESTER", "STORE_MANAGER")
]

#: This platform's capability roster and the blocks each capability drives.
CAPABILITIES = [
    {
        "id": "collection_planning_tracking",
        "entity": "collection_planning_tracking",
        "words": "Plan, schedule and track coffee-waste collections from cafes and other sources through to delivery at the factory.",
        "block_ids": ["task_listing", "geolocation_tracking", "workflow"],
        "gap": False,
    },
    {
        "id": "batch_production_tracking",
        "entity": "batch_production_tracking",
        "words": "Follow compost batches through production stages, curing and quality checks, with the readings and results each stage produced.",
        "block_ids": ["workflow", "task_listing", "audit"],
        "gap": False,
    },
    {
        "id": "catalog_pricing_orders",
        "entity": "catalog_pricing_orders",
        "words": "Manage the product catalog, price lists, customer records and customer orders, including order lines and totals.",
        "block_ids": ["vendor_catalog", "workflow"],
        "gap": False,
    },
    {
        "id": "invoicing_tunisian_vat",
        "entity": "invoicing_tunisian_vat",
        "words": "Generate invoices in Tunisian dinar with Tunisian VAT applied according to the customer's own rate, with the VAT breakdown and totals.",
        "block_ids": ["billing", "finance_canonical_model", "finance_coa_governance"],
        "gap": False,
    },
    {
        "id": "internal_staff_access",
        "entity": "internal_staff_access",
        "words": "Provide secure login and role-based access for the 5-10 internal staff across collection, production, sales and finance.",
        "block_ids": ["auth", "multi_tenant_rbac"],
        "gap": False,
    },
    {
        "id": "operational_dashboard",
        "entity": "operational_dashboard",
        "words": "Show an operational dashboard of collection status, batch progress, orders and invoices for internal staff.",
        "block_ids": ["dashboard", "analytics"],
        "gap": False,
    },
]

BINDINGS = [
    {"capability_id": row["id"], "block_ids": list(row["block_ids"]), "gap": row["gap"]}
    for row in CAPABILITIES
]

CATALOG: Dict[str, Any] = {
    "kernel": "COLLECTOR",
    "title": _TITLES["COLLECTOR"],
    "mandate": _MANDATES["COLLECTOR"],
    "agent": _AGENTS["COLLECTOR"],
    "resolved_blocks": sorted({b for row in CAPABILITIES for b in row["block_ids"]}),
    "gaps": [row["id"] for row in CAPABILITIES if row["gap"]],
    "bindings": BINDINGS,
}

GATES: Dict[str, Any] = {
    "kernel": "TESTER",
    "title": _TITLES["TESTER"],
    "mandate": _MANDATES["TESTER"],
    "agent": _AGENTS["TESTER"],
    "runs_over_http": False,
    "suite": [
        {"file": "tests/test_smoke.py", "covers": "import, offline dispatch load, handle() returns a mapping", "gated": True},
        {"file": "tests/test_routes.py", "covers": "HTTP answers for /health, kernel jobs and each capability POST", "gated": True},
        {"file": "tests/test_data_lifecycle.py", "covers": "Alembic up/down on populated v1, restore drill, parallel writes", "gated": True},
        {"file": "tests/test_deploy.py", "covers": "fail-closed /health, correlation logs, revision identity", "gated": True},
        {"file": "tests/test_domain_acceptance.py", "covers": "ten business outcomes through execute_action", "marker": "pilot", "gated": False},
        {"file": "tests/test_negative_floor.py", "covers": "counter-cases: invalid values, cross-tenant writes, boundaries, fuzzed payloads", "gated": False},
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
    """CLONER -- the pinned vendor lock, read live from the checkout, plus
    what THIS platform was built from. Read-only: no kernel job runs here."""
    payload: Dict[str, Any] = dict(_job("CLONER"))
    payload["lock"] = _read_workspace_json("blocks.lock.json") or {
        "schema": "blocks.lock.v1",
        "blocks": {},
    }
    root = Path(__file__).resolve().parents[1]
    base = root / "vendor" / "blocks"
    vendored = sorted(p.name for p in base.glob("*") if p.is_dir()) if base.is_dir() else []
    payload["capabilities"] = [dict(row) for row in CAPABILITIES]
    payload["bindings"] = [dict(row) for row in BINDINGS]
    payload["entities"] = {row["id"]: row["entity"] for row in CAPABILITIES}
    payload["vendored_blocks"] = vendored
    payload["count"] = len(vendored)
    payload["blocks"] = sorted({b for row in CAPABILITIES for b in row["block_ids"]})
    return payload


def provenance() -> Dict[str, Any]:
    """STORE_MANAGER -- the clone register and the build provenance."""
    payload: Dict[str, Any] = dict(_job("STORE_MANAGER"))
    payload["build"] = _read_workspace_json("docs/build_provenance.json") or {}
    lock = _read_workspace_json("blocks.lock.json") or {}
    payload["clones"] = lock.get("blocks") or {}
    payload["catalog"] = CATALOG
    payload["gates"] = GATES
    payload["capabilities"] = [row["id"] for row in CAPABILITIES]
    payload["inventory"] = inventory()
    payload["store_ops"] = []
    return payload
# --- BEGIN factory block: stamped by the Factory, edits here are replaced ---
import json


from pathlib import Path


from typing import Any, Dict, Optional


JOBS = [{'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'http_routes': ['GET /v1/catalog'], 'gate': 'every referenced block id is dual-registered; gaps enumerated', 'read_only': True}, {'kernel': 'CLONER', 'title': 'Block stocker', 'mandate': "Vendor each resolved block's source at a pinned commit, plus the local dispatch runtime those shims stand on, plus the kit packs the Factory shelf assigns those blocks to, so handlers import blocks instead of calling the store over HTTP. Write only vendor/**, kits/**, and blocks.lock.json. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/inventory'], 'gate': 'every vendored block imports with no network configured', 'read_only': False}, {'kernel': 'WRITER', 'title': 'Platform manufacturer', 'mandate': "Manufacture the platform over the vendored stock: capability handlers, domain models, persistence, the HTTP surface (including each kernel's job routes), UI wiring, and GENERATE logic for the gaps the collector reported. The coding agent writes those artifacts inside WRITER lanes. Do not touch tests/ or vendor/.", 'agent': 'manufacture', 'http_routes': ['GET /v1/capabilities', 'POST /v1/{capability}', 'GET /v1/{capability}', 'GET /v1/{capability}/{id}', 'PUT /v1/{capability}/{id}', 'DELETE /v1/{capability}/{id}', 'POST /v1/work_queue', 'POST /v1/work_queue/{id}/process', 'GET /v1/work_queue'], 'gate': 'workspace imports and type-checks clean', 'read_only': False}, {'kernel': 'TESTER', 'title': 'Acceptance inspector', 'mandate': "Write and run the code-phase suite against what the WRITER produced (imports, dispatch load, models, routes answer JSON, handle() returns a mapping) and bounce those failures for another writer pass. Store-backed execute-all is pilot coverage, not this gate. The harness's acceptance IS the tester — do not consult the coding agent for extra cases. Never patch app/. Never run the suite over HTTP — GET /v1/gates describes coverage only.", 'agent': 'none', 'http_routes': ['GET /v1/gates'], 'gate': "code-phase suite green (pytest -m 'not pilot')", 'read_only': False}, {'kernel': 'STORE_MANAGER', 'title': 'Store registrar', 'mandate': "Keep the store's books: register what this platform cloned and at which commit. This minimal form records the clone register and applies no store op. Harvesting improvements back upstream and admitting client-driven net-new capability remain unbuilt. Exact answers — no agent.", 'agent': 'none', 'http_routes': ['GET /v1/provenance'], 'gate': 'store_manager.assert_store_op_allowed passes for every op applied', 'read_only': False}]


CATALOG = {'kernel': 'COLLECTOR', 'title': 'Binding surveyor', 'mandate': "Emit intake_blueprint.v1 (COLLECTOR output IS that object — vertical, capabilities with customer words + normalized id, roles/users, data sources, integrations, constraints, done_when, each field carrying the chat turn it came from). Resolve each capability's declared block ids into harvestable contracts. Name every capability with no block as an explicit gap so the WRITER authors that logic — never drop it from the plan. Consult the coding agent for a report-only endorse/mismatch review of each binding. Do not invent block ids, do not mutate the plan, and write nothing.", 'agent': 'consult', 'resolved_blocks': ['task_listing', 'geolocation_tracking', 'workflow', 'audit', 'vendor_catalog', 'billing', 'finance_canonical_model', 'finance_coa_governance', 'auth', 'multi_tenant_rbac', 'dashboard', 'analytics'], 'gaps': [], 'bindings': [{'capability_id': 'collection_planning_tracking', 'block_ids': ['task_listing', 'geolocation_tracking', 'workflow'], 'gap': False}, {'capability_id': 'batch_production_tracking', 'block_ids': ['workflow', 'task_listing', 'audit'], 'gap': False}, {'capability_id': 'catalog_pricing_orders', 'block_ids': ['vendor_catalog', 'workflow'], 'gap': False}, {'capability_id': 'invoicing_tunisian_vat', 'block_ids': ['billing', 'finance_canonical_model', 'finance_coa_governance'], 'gap': False}, {'capability_id': 'internal_staff_access', 'block_ids': ['auth', 'multi_tenant_rbac'], 'gap': False}, {'capability_id': 'operational_dashboard', 'block_ids': ['dashboard', 'analytics'], 'gap': False}], 'agent_reviews': [{'capability_id': 'collection_planning_tracking', 'block_ids': ['task_listing', 'geolocation_tracking', 'workflow'], 'verdict': 'endorse', 'reason': 'task_listing geo-qualification plus geolocation_tracking geofence/ETA and workflow orchestration plausibly serve collection planning and route tracking.'}, {'capability_id': 'batch_production_tracking', 'block_ids': ['workflow', 'task_listing', 'audit'], 'verdict': 'mismatch', 'reason': 'task_listing is a marketplace listing primitive; batch production tracking needs batch/process state, not listing/price-band logic. workflow+audit fit, the listing block is strained.'}, {'capability_id': 'catalog_pricing_orders', 'block_ids': ['vendor_catalog', 'workflow'], 'verdict': 'endorse', 'reason': 'vendor_catalog gives vendor/service-area/item/Decimal pricing/search and workflow chains it; covers catalog and pricing, orders only lightly but plausible.'}, {'capability_id': 'invoicing_tunisian_vat', 'block_ids': ['billing', 'finance_canonical_model', 'finance_coa_governance'], 'verdict': 'mismatch', 'reason': 'billing handles subscriptions/usage invoices; no explicit Tunisian VAT rate/regime logic and no tax determination surface across the three blocks — engineer would flag VAT compliance at tender.'}, {'capability_id': 'internal_staff_access', 'block_ids': ['auth', 'multi_tenant_rbac'], 'verdict': 'endorse', 'reason': 'auth keys/rate-limit/permission checks plus fail-closed multi-tenant RBAC directly serve staff access control.'}, {'capability_id': 'operational_dashboard', 'block_ids': ['dashboard', 'analytics'], 'verdict': 'endorse', 'reason': 'dashboard widgets/layout/streams plus analytics event tracking and reports plausibly serve an operational dashboard.'}], 'agent_model': 'deepseek-chat'}


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
