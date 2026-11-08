"""One compliance view over claims, delay exposure, ITPs, documents, security.

The snapshot is read from the tenant's own persisted records (never from a
client-supplied total), rendered through the dashboard block, tracked as a
metric, and pushed as an MCP notification. Every figure drills down to the
clause or BOQ item that governs it.
"""

from __future__ import annotations

from datetime import date

from app import contract_terms as terms
from app import formulas
from app import store
from app.actions._support import (
    as_float, as_int, block_result, check, input_digest, ok, require_payload,
    round_money, tenant_id,
)
from app.block_inputs import default_block_action
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "compliance_dashboard"
ENTITY = "compliance_dashboard"
BLOCK_IDS = ["dashboard", "analytics", "notification"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "store:list_all", "app.contract_terms", "app.formulas"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]


DECLARED_FIGURES = (
    "claims_open",
    "delay_exposure",
    "itp_completion_ratio",
    "documents_registered",
    "security_valid",
)


def _rows(entity, tenant):
    try:
        return store.list_all(entity, tenant_id=tenant)
    except Exception:  # noqa: BLE001 -- an empty view is a real view
        return []


def _delay_exposure(delays):
    total = 0.0
    for row in delays:
        amount = as_float(row.get("delay_damages_amount"))
        if amount <= 0:
            accepted = as_float(row.get("accepted_contract_amount")) or terms.ACCEPTED_CONTRACT_AMOUNT
            days = max(0.0, as_float(row.get("delay_days")) - as_float(row.get("extension_days")))
            amount = formulas.delay_damages(accepted, days)["value"]
        total += amount
    return total


def _security_valid(securities):
    today = date.today()
    for row in securities:
        secured = as_float(row.get("secured_amount"))
        required = as_float(row.get("required_amount")) or (
            as_float(row.get("accepted_contract_amount")) * terms.PERFORMANCE_SECURITY_RATIO
        ) or terms.ACCEPTED_CONTRACT_AMOUNT * terms.PERFORMANCE_SECURITY_RATIO
        expiry = str(row.get("expiry_date") or "")
        try:
            expiry_ok = date.fromisoformat(expiry[:10]) >= today
        except ValueError:
            expiry_ok = True
        if required and secured / required >= 1.0 and expiry_ok:
            return True
    return False


def _snapshot(tenant):
    claims = _rows("progress_claim_processing", tenant)
    delays = _rows("delay_damages_tracking", tenant)
    itps = _rows("qa_itp_records", tenant)
    documents = _rows("document_register", tenant)
    securities = _rows("performance_security_tracking", tenant)

    claims_open = len([row for row in claims if str(row.get("status")) != "closed"])
    exposure = _delay_exposure(delays) if delays else 0.0
    passed = len([row for row in itps if str(row.get("result") or "").lower() in ("pass", "passed", "accepted")])
    completion = (passed / len(itps)) if itps else 0.0
    security_valid = _security_valid(securities)
    return {
        "claims_open": claims_open,
        "claims_total": len(claims),
        "delay_events": len(delays),
        "delay_exposure": round_money(exposure),
        "itp_total": len(itps),
        "itp_completion_ratio": round(completion, 4),
        "documents_registered": len(documents),
        "securities_tracked": len(securities),
        "security_valid": security_valid,
    }


def handle(payload):
    payload = require_payload(payload)
    tenant = tenant_id()
    view = _snapshot(tenant)

    dashboard_answer = execute(
        "dashboard",
        {
            "widgets": [
                {"id": "claims", "type": "status_grid", "title": "Progress claims"},
                {"id": "delay", "type": "chart", "title": "Delay-damages exposure"},
                {"id": "itp", "type": "chart", "title": "ITP completion"},
                {"id": "documents", "type": "status_grid", "title": "Document register"},
                {"id": "security", "type": "status_grid", "title": "Performance security"},
            ]
        },
        action=BLOCK_DEFAULT_ACTIONS.get("dashboard"),
    )
    stopped = check("dashboard", dashboard_answer)
    if stopped:
        return stopped
    rendered = block_result(dashboard_answer)

    metric_answer = execute(
        "analytics",
        {
            "metric": "compliance.claims_open",
            "value": view["claims_open"],
            "tags": {"period": str(payload.get("period") or ""), "tenant": tenant},
        },
        action=BLOCK_DEFAULT_ACTIONS.get("analytics"),
    )
    stopped = check("analytics", metric_answer)
    if stopped:
        return stopped
    metric = block_result(metric_answer)

    notice_answer = execute(
        "notification",
        {
            "channel": "mcp",
            "block": "analytics",
            "tool": "analytics",
            "params": {"action": "track_event"},
            "payload": {
                "metric": "compliance.snapshot",
                "value": view["delay_exposure"],
                "tags": {"claims_open": view["claims_open"]},
            },
            "message": "Compliance snapshot: %d open claims, exposure %s"
            % (view["claims_open"], view["delay_exposure"]),
        },
        action=BLOCK_DEFAULT_ACTIONS.get("notification"),
    )
    stopped = check("notification", notice_answer)
    if stopped:
        return stopped
    notice = block_result(notice_answer)

    # Totals are derived from the tenant's own records; a client-supplied
    # snapshot is displayed as its own note and never merged into the view.
    note = str(payload.get("snapshot") or "")
    declared = {name: payload[name] for name in DECLARED_FIGURES if name in payload}

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "reference": str(payload.get("reference") or ""),
            "period": payload.get("period") or "",
            "snapshot": view,
            "declared": declared,
            "client_note": note,
            "widgets_rendered": len(rendered.get("widgets") or []),
            "metric_tracked": bool(metric.get("tracked")),
            "notice_sent": bool(notice.get("sent")),
            "declared_figures": declared,
            "input_digest": input_digest(payload),
            "drill_down": {
                "claims": terms.clause_citation(terms.RETENTION),
                "delay": terms.clause_citation(terms.DELAY_DAMAGES),
                "itp": terms.clause_citation(terms.DEFECTS_NOTIFICATION),
                "documents": terms.document_citation(terms.BOQ_FILENAME),
                "security": terms.clause_citation(terms.PERFORMANCE_SECURITY),
            },
            "citations": [
                terms.clause_citation(terms.DELAY_DAMAGES),
                terms.clause_citation(terms.RETENTION),
                terms.clause_citation(terms.PERFORMANCE_SECURITY),
            ],
            "authority": "documents (layer 2, precedence.v1)",
        }
    )
