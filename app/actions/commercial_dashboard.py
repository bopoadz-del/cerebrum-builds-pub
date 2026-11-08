"""commercial_dashboard -- the project's commercial position in one place.

Aggregates the tenant's persisted claims, delay assessments and QA/ITP
records into cumulative certified amounts, retention balances, delay-damages
exposure and open QA items. The operator surface is built on the dashboard
block's own render contract; the metrics event and portfolio rollup are
driven from the same numbers.

READS   app.store for the tenant's persisted records; the request snapshot
        supplies the figures when no records exist yet.
WRITES  evidence artifacts under STORAGE_PATH/workspace; the ROUTE persists
        the snapshot, never this handler.
NEVER   reports a certified amount that is not backed by a stored claim or
        the caller's snapshot.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import contract_data, formulas, store
from app import capability_support as _support
from app.capability_support import ok, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "commercial_dashboard"
ENTITY = "commercial_dashboard"
BLOCK_IDS = ["dashboard", "analytics", "portfolio_rollup"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}


def _rows(entity: str, tenant: str) -> List[Dict[str, Any]]:
    try:
        return store.list_all(entity, tenant_id=tenant)
    except Exception:  # noqa: BLE001 - a first run has no table yet
        return []


def _claim_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    gross = 0.0
    retention = 0.0
    net = 0.0
    properties: List[Dict[str, Any]] = []
    for row in rows:
        try:
            row_gross = float(row.get("gross_amount") or 0.0)
        except (TypeError, ValueError):
            row_gross = 0.0
        if row_gross <= 0:
            # A claim stored as quantity x rate (no gross stated) is still a
            # certified amount: read the BOQ rate when the record omits one.
            quantity = _support.number_of(row, "claimed_quantity", 0.0)
            rate = _support.number_of(row, "rate", 0.0)
            if rate <= 0:
                line = contract_data.boq_item(_support.text_of(row, "boq_item").upper())
                rate = float((line or {}).get("rate") or 0.0)
            if quantity <= 0:
                line = contract_data.boq_item(_support.text_of(row, "boq_item").upper())
                quantity = float((line or {}).get("quantity") or 0.0)
            row_gross = round(quantity * rate, 2)
        pct = row.get("retention_pct")
        try:
            row_pct = float(pct) if pct not in (None, "") else contract_data.RETENTION_PCT
        except (TypeError, ValueError):
            row_pct = contract_data.RETENTION_PCT
        row_retention = formulas.retention_amount(row_gross, row_pct)
        row_net = formulas.certified_amount(row_gross, row_retention)
        gross += row_gross
        retention += row_retention
        net += row_net
        properties.append(
            {
                "id": row.get("reference") or str(row.get("id")),
                "value": row_net,
                "status": str(row.get("status") or "open"),
            }
        )
    return {
        "gross": round(gross, 2),
        "retention": round(retention, 2),
        "net": round(net, 2),
        "properties": properties,
    }


def _delay_days(row: Dict[str, Any]) -> int:
    """The delay a stored assessment carries: stated, else derived from dates.

    A record that names a commencement date and an assessment date has its
    delay decided by the contract's Time for Completion, exactly as the
    delay-damages capability computes it -- the dashboard must not read a
    missing ``delay_days`` as "no delay".
    """
    stated = _support.int_of(row, "delay_days", -1)
    if stated >= 0:
        return stated
    commencement = _support.as_date(row.get("commencement_date"))
    if commencement is None:
        return 0
    assessed = _support.as_date(row.get("assessment_date")) or _support.as_date(
        row.get("updated_at")
    )
    if assessed is None:
        from datetime import date

        assessed = date.today()
    elapsed = max(0, (assessed - commencement).days)
    extension = max(0, _support.int_of(row, "extension_days", 0))
    allowable = contract_data.TIME_FOR_COMPLETION_DAYS + extension
    return max(0, elapsed - allowable)


def _delay_metrics(rows: List[Dict[str, Any]]) -> float:
    total = 0.0
    for row in rows:
        accepted = _support.number_of(row, "accepted_contract_amount", 0.0)
        if accepted <= 0:
            accepted = contract_data.boq_total()
        daily = _support.number_of(row, "daily_rate_pct", 0.0) or contract_data.DELAY_DAMAGES_DAILY_PCT
        cap = _support.number_of(row, "cap_pct", 0.0) or contract_data.DELAY_DAMAGES_CAP_PCT
        total += formulas.delay_damages(accepted, daily, _delay_days(row), cap)["damages"]
    return round(total, 2)


def _taking_over_date(rows: List[Dict[str, Any]]) -> Any:
    """The project's Taking-Over date, from the ITP records that state one."""
    from datetime import date

    dates = [
        _support.as_date(row.get("taking_over_date"))
        for row in rows
        if _support.as_date(row.get("taking_over_date")) is not None
    ]
    return min(dates) if dates else None


def _retention_release(withheld: float, qa_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How much of the withheld retention the contract has released.

    Clause 14.3 releases the split percentage at Taking-Over and the balance
    at the end of the Defects Notification Period. Both dates are read from
    the contract and from the ITP record that states Taking-Over -- never
    assumed.
    """
    from datetime import date, timedelta

    split = contract_data.RETENTION_RELEASE_SPLIT_PCT
    taking_over = _taking_over_date(qa_rows)
    released_pct = 0.0
    if taking_over is not None:
        today = date.today()
        if today >= taking_over:
            released_pct += split
        dnp_end = taking_over + timedelta(days=contract_data.DEFECTS_NOTIFICATION_DAYS)
        if today >= dnp_end:
            released_pct += split
    released_pct = min(100.0, released_pct)
    released = round(withheld * released_pct / 100.0, 2)
    return {
        "taking_over_date": taking_over.isoformat() if taking_over else None,
        "released_pct": round(released_pct, 2),
        "released": released,
        "held": round(withheld - released, 2),
        "split_pct": split,
        "clause": contract_data.clause_number("retention"),
    }


def _qa_open(rows: List[Dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        status = str(row.get("status") or "open")
        result = str(row.get("test_result") or "pending").lower()
        if status != "closed" and result in ("pending", "fail"):
            count += 1
    return count


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    principal = _support.text_of(record, "_principal_id", "principal_id") or "commercial-manager"
    tenant = _support.text_of(record, "_tenant_id", "tenant_id") or "local"
    period = _support.text_of(record, "period") or "current"

    claims = _rows("progress_claim_management", tenant)
    delays = _rows("delay_damages_tracking", tenant)
    qa_records = _rows("qa_itp_records", tenant)

    computed = _claim_metrics(claims)
    cumulative = computed["net"]
    retention = computed["retention"]
    delay_exposure = _delay_metrics(delays)
    qa_open = _qa_open(qa_records)
    source = "persisted_records" if (claims or delays or qa_records) else "request_snapshot"
    release = _retention_release(retention, qa_records) if claims else {
        "taking_over_date": None,
        "released_pct": 0.0,
        "released": 0.0,
        "held": retention,
        "split_pct": contract_data.RETENTION_RELEASE_SPLIT_PCT,
        "clause": contract_data.clause_number("retention"),
    }
    retention = release["held"]
    if not claims:
        cumulative = _support.number_of(record, "cumulative_certified", 0.0)
        retention = _support.number_of(record, "retention_balance", 0.0)
        release["held"] = retention
    if not delays:
        delay_exposure = _support.number_of(record, "delay_exposure", 0.0)
    if not qa_records:
        qa_open = _support.int_of(record, "qa_open_items", 0)
    claim_status = _support.text_of(record, "claim_status") or (
        "closed" if claims and all(str(row.get("status")) == "closed" for row in claims) else "open"
    )

    properties = computed["properties"] or [
        {
            "id": reference,
            "value": cumulative,
            "status": claim_status,
        }
    ]
    widgets = [
        {
            "id": "cumulative_certified",
            "type": "metric",
            "title": "Cumulative certified",
            "value": cumulative,
            "currency": contract_data.currency_label(),
        },
        {
            "id": "retention_balance",
            "type": "metric",
            "title": "Retention balance",
            "value": retention,
            "currency": contract_data.currency_label(),
        },
        {
            "id": "delay_exposure",
            "type": "metric",
            "title": "Delay-damages exposure",
            "value": delay_exposure,
            "currency": contract_data.currency_label(),
        },
        {
            "id": "qa_open_items",
            "type": "metric",
            "title": "QA/ITP open items",
            "value": qa_open,
        },
        {
            "id": "claim_count",
            "type": "metric",
            "title": "Claims recorded",
            "value": len(claims),
        },
    ]
    snapshot = {
        "reference": reference,
        "period": period,
        "claim_status": claim_status,
        "cumulative_certified": round(cumulative, 2),
        "retention_balance": round(retention, 2),
        "retention_withheld": round(computed["retention"], 2),
        "retention_released": release["released"],
        "retention_release": release,
        "delay_exposure": round(delay_exposure, 2),
        "qa_open_items": qa_open,
        "claim_count": len(claims),
        "delay_count": len(delays),
        "qa_count": len(qa_records),
        "data_source": source,
        "currency": contract_data.currency_label(),
        "widgets": widgets,
        "citations": [contract_data.CONTRACT_DOCUMENT, contract_data.BOQ_DOCUMENT],
        "authority": "layer 3 formulas",
    }

    inputs: Dict[str, Dict[str, Any]] = {
        "dashboard": {"user_id": tenant, "layout": "grid"},
        "analytics": {"metric": "commercial_cumulative_certified", "value": cumulative},
        "portfolio_rollup": {"properties": properties},
    }
    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        from app.capability_support import refuse

        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    workspace = _support.workspace_dir(CAPABILITY_ID)
    artifact = _support.artifact_name("dashboard", snapshot)
    _support.write_artifact(workspace, artifact, snapshot)
    result = {
        **snapshot,
        "dashboard_file": artifact,
        "block_evidence": {
            "dashboard_rendered": isinstance(answers.get("dashboard"), dict)
            and answers["dashboard"].get("ok") is not False,
            "analytics_tracked": isinstance(answers.get("analytics"), dict)
            and answers["analytics"].get("ok") is not False,
            "portfolio_rolled_up": isinstance(answers.get("portfolio_rollup"), dict)
            and answers["portfolio_rollup"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
