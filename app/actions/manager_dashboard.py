"""One manager dashboard over cost movements, revisions and alerts."""

from __future__ import annotations

from typing import Any, Dict

from app import formulas, store
from app.actions._common import block_failure, envelope
from app.dispatch import execute
from app.tenancy import current_tenant

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "manager_dashboard"
ENTITY = "manager_dashboard"
BLOCK_IDS = ["dashboard", "analytics", "aesthetic_kit"]
BLOCK_DEFAULT_ACTIONS = {"dashboard": "render", "analytics": "get_metrics", "aesthetic_kit": None}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "database", "scope": "tenant_records"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    tenant = current_tenant()
    plant = str(record.get("plant") or "all")
    alerts = store.list_all("cost_price_movement_alerts", tenant_id=tenant)
    revisions = store.list_all("document_revision_nudges", tenant_id=tenant)
    costs = store.list_all("supplier_cost_and_parts_pricing", tenant_id=tenant)
    open_alerts = [row for row in alerts if row.get("status") != "closed"]
    markups = []
    for row in costs:
        try:
            cost = float(row.get("unit_cost_mad") or 0)
            price = float(row.get("price_mad") or 0)
        except (TypeError, ValueError):
            continue
        if cost > 0 and price > 0:
            markups.append(formulas.markup_on_cost(price, cost))

    board = execute(
        "dashboard",
        {"user_id": plant, "plant": plant},
        action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
    )
    refused = block_failure("dashboard", board)
    if refused:
        return refused

    metrics = execute(
        "analytics",
        {},
        action=BLOCK_DEFAULT_ACTIONS.get("analytics"),
    )
    refused = block_failure("analytics", metrics)
    if refused:
        return refused

    kit = execute(
        "aesthetic_kit",
        {"question": plant, "figures": {}, "state": {}, "events": [], "hooks": []},
        action=BLOCK_DEFAULT_ACTIONS.get("aesthetic_kit"),
    )
    refused = block_failure("aesthetic_kit", kit)
    if refused:
        return refused

    return envelope(
        {
            "plant": plant,
            "widgets": len(board.get("widgets") or []),
            "theme": board.get("theme"),
            "alerts_open": len(open_alerts),
            "cost_records": len(costs),
            "average_markup_ratio": round(sum(markups) / len(markups), 6) if markups else None,
            "revisions": len(revisions),
            "metrics_available": bool(metrics),
            "layout": (kit.get("result") or {}).get("verdict") if isinstance(kit.get("result"), dict) else "refused",
            "include_alerts": bool(record.get("include_alerts", True)),
        },
        record,
    )
