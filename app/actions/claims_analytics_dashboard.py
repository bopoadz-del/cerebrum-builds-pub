"""Claims portfolio analytics: certified value, retention, delay exposure.

The dashboard reports the tenant's contract position from the records the
other capabilities persisted — certificates, delay assessments, ITP records,
the document register and the security/retention ledger — so an operator sees
what is actually stored rather than a total typed into a form. The BOQ value
is read from the uploaded bill when the caller supplies its extract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import boq, formulas, store
from app.actions._blocks import call
from app.authority import label

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "claims_analytics_dashboard"
ENTITY = "claims_analytics_dashboard"
BLOCK_IDS = ["dashboard", "analytics", "portfolio_rollup"]


def _rows(entity: str, tenant_id: str) -> List[Dict[str, Any]]:
    """The tenant's stored records for an entity; empty when none are readable.

    A handler invoked directly (outside the HTTP route) may carry no tenant;
    it then aggregates nothing rather than reaching another tenant's rows.
    """
    if not str(tenant_id or "").strip():
        return []
    try:
        return store.list_all(entity, str(tenant_id))
    except Exception:  # noqa: BLE001 - an unreadable store contributes no rows
        return []


def _money(value: Any) -> float:
    return round(float(value or 0.0), 2)


def _closed(record: Dict[str, Any]) -> bool:
    return str(record.get("status") or "").strip().lower() == "closed"


def _approved(record: Dict[str, Any]) -> bool:
    return str(record.get("approval_state") or "").strip().lower() == "approved"


def _claim_gross(record: Dict[str, Any]) -> float:
    """A stored certificate's gross, re-derived from the bill it cites.

    The route persists the request, so the stored row carries the measured
    quantity, item and BOQ extract rather than the answer: the position is
    re-derived here through the same source-of-record rule the certificate
    applied. A bill line the extract no longer contains contributes nothing.
    """
    quantity = float(record.get("measured_quantity") or 0.0)
    rate = float(record.get("boq_rate") or 0.0)
    source = str(record.get("source_text") or "")
    if source.strip():
        line = boq.line_for(source, str(record.get("boq_item") or ""))
        if line is None:
            return 0.0
        bill_quantity = line.get("quantity")
        bill_rate = line.get("rate")
        if bill_quantity is not None:
            quantity = min(quantity, float(bill_quantity))
        if bill_rate is not None:
            rate = float(bill_rate)
        return _money(quantity * rate)
    return _money(record.get("amount_certified"))


def _claim_retention(record: Dict[str, Any], gross: float) -> float:
    rate = float(record.get("retention_rate") or 0.0)
    rate = min(max(rate, 0.0), 1.0)
    return _money(gross * rate)


def handle(payload: Optional[Dict[str, Any]] = None, tenant_id: str = "") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "record")
    stored_figure = _money(record.get("certified_total"))
    stated_retention = _money(record.get("retention_total"))
    blocks: Dict[str, Any] = {}

    claims = _rows("progress_claims", tenant_id)
    delays = _rows("delay_damages_tracking", tenant_id)
    itps = _rows("qa_itp_records", tenant_id)
    register = _rows("document_register", tenant_id)
    ledger = _rows("payment_security_and_retention_ledger", tenant_id)

    certified = 0.0
    retained = 0.0
    for row in claims:
        gross = _claim_gross(row)
        certified += gross
        retained += _claim_retention(row, gross)
    certified, retained = _money(certified), _money(retained)
    if claims:
        certified_from = "progress_claims"
    else:
        certified, retained = stored_figure, stated_retention
        certified_from = "caller"
    claims_count = len(claims) if claims else int(record.get("claims_count") or 0)

    boq_value = 0.0
    boq_items = 0
    source_text = str(record.get("boq_source_text") or "")
    if source_text.strip():
        bill = boq.total(source_text)
        boq_value = _money(bill.get("total"))
        boq_items = int(bill.get("items") or 0)

    exposure = _money(max((float(row.get("damages_assessed") or 0.0) for row in delays), default=0.0))
    delay_days = max([int(row.get("delay_days") or 0) for row in delays] + [int(record.get("delay_days") or 0)])

    itp_total = len(itps)
    itp_closed = sum(1 for row in itps if _closed(row))
    itp_failed = sum(1 for row in itps if str(row.get("outcome") or "").lower() == "fail")

    register_total = len(register)
    register_approved = sum(1 for row in register if _approved(row))

    security_held = _money(sum(
        float(row.get("amount_held") or 0.0) for row in ledger
        if str(row.get("entry_type") or "") == "performance_security"
    ))
    retention_ledger = _money(sum(
        float(row.get("amount_held") or 0.0) for row in ledger
        if str(row.get("entry_type") or "") == "retention"
    ))

    net = formulas.net_certified(certified, retained)

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
        "claims_count": claims_count,
        "certified_total": certified,
        "retention_total": retained,
        "earned_value": _money(record.get("earned_value")),
        "delay_days": delay_days,
        "boq_source_text": source_text,
    }
    computed = {
        "certified_to_date": certified,
        "certified_source": certified_from,
        "boq_value": boq_value,
        "boq_items": boq_items,
        "certified_vs_boq_ratio": round(certified / boq_value, 4) if boq_value else 0.0,
        "certified_total": certified,
        "retention_total": retained,
        "net_certified": _money(net["value"]),
        "net_formula": net["address"],
        "retention_ratio": round(retained / certified, 4) if certified else 0.0,
        "average_claim": round(certified / claims_count, 2) if claims_count else 0.0,
        "delay_damages_exposure": exposure,
        "delay_records": len(delays),
        "delay_days": delay_days,
        "itp_total": itp_total,
        "itp_closed": itp_closed,
        "itp_open": itp_total - itp_closed,
        "itp_failed": itp_failed,
        "register_total": register_total,
        "register_approved": register_approved,
        "register_completeness": round(register_approved / register_total, 4) if register_total else 0.0,
        "security_held": security_held,
        "retention_ledger_held": retention_ledger,
        "rollup_total": blocks["portfolio_rollup"]["total_value"],
        "dashboard_widgets": blocks["dashboard"]["widgets"],
        "sources": {
            "progress_claims": len(claims),
            "delay_damages_tracking": len(delays),
            "qa_itp_records": itp_total,
            "document_register": register_total,
            "payment_security_and_retention_ledger": len(ledger),
        },
    }
    return {
        "ok": True,
        "capability_id": CAPABILITY_ID,
        "record": stored,
        "computed": computed,
        "blocks": blocks,
        "authority": label("formulas"),
    }
