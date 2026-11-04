"""Claims portfolio analytics: certified value, retention, delay exposure."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app import formulas
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "claims_analytics_dashboard"
ENTITY = "claims_analytics_dashboard"
BLOCK_IDS = ["dashboard", "analytics", "portfolio_rollup"]


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    certified = round(float(record.get("certified_total") or 0.0), 2)
    retained = round(float(record.get("retention_total") or 0.0), 2)
    net = formulas.net_certified(certified, retained)
    blocks: Dict[str, Any] = {}

    rendered, error = call("dashboard", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    widgets = rendered.get("widgets") or []
    blocks["dashboard"] = {
        "widgets": len(widgets),
        "layout": (rendered.get("layout") or {}).get("name"),
    }

    tracked, error = call("analytics", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["analytics"] = {
        "metric": tracked.get("metric"),
        "tracked": bool(tracked.get("tracked")),
    }

    rollup, error = call("portfolio_rollup", CAPABILITY_ID, record, tenant_id)
    if error:
        return {"ok": False, "error": error, "capability_id": CAPABILITY_ID}
    blocks["portfolio_rollup"] = {
        "total_value": rollup.get("total_value"),
        "count": rollup.get("count"),
        "by_status": rollup.get("by_status") or {},
    }

    stored = {
        "reference": reference,
        "status": str(record.get("status") or "open"),
        "period": str(record.get("period") or ""),
        "claims_count": int(record.get("claims_count") or 0),
        "certified_total": certified,
        "retention_total": retained,
        "earned_value": round(float(record.get("earned_value") or 0.0), 2),
        "delay_days": int(record.get("delay_days") or 0),
    }
    computed = {
        "certified_total": certified,
        "retention_total": retained,
        "net_certified": round(float(net["value"]), 2),
        "net_formula": net["address"],
        "retention_ratio": round(retained / certified, 4) if certified else 0.0,
        "average_claim": round(certified / stored["claims_count"], 2) if stored["claims_count"] else 0.0,
        "rollup_total": blocks["portfolio_rollup"]["total_value"],
        "dashboard_widgets": blocks["dashboard"]["widgets"],
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("formulas"),
    }
