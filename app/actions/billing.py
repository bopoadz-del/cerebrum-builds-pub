"""Billing capability.

The vendored billing block records metered usage and prices it against its own
plan limits.  The capability supplies the owner and the units from the domain
record, then reports the cost the block computed and the plan limit the block
declares in its own ``PLANS`` table.  The route's plan vocabulary refuses a
plan outside that table (HTTP 422); if the handler is reached with a plan the
block does not declare it reports no quota rather than borrowing another
plan's limit.  The capability adds no price or quota of its own.

SCALE: one usage record per call.
READS: caller fields; the billing block's declared plan contract.
WRITES: the usage record in the response; the route persists the record.
NEVER: a price or a quota the block did not declare.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.action_common import as_int, block_failed, fail, ok, refusal_text
from app.dispatch import _block_instance, execute

CAPABILITY_ID = "billing"
ENTITY = "billing"
BLOCK_IDS = ["billing"]
BLOCK_DEFAULT_ACTIONS = {"billing": "record_usage"}
AUTHORED_BY = "codewhale exec"


def _plan_table() -> Dict[str, Any]:
    """The block's own PLANS declaration, read from the locked block."""
    module, instance = _block_instance("billing")
    plans = getattr(instance, "PLANS", None)
    if not isinstance(plans, dict) or not plans:
        return {}
    return plans


def _limit(plan: str, plans: Dict[str, Any]) -> Optional[Any]:
    spec = plans.get(plan) or {}
    if "requests" not in spec:
        return None
    value = spec.get("requests")
    if isinstance(value, float) and value == float("inf"):
        return None  # declared unlimited; reported as null, never a number
    return value


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "billing")
    owner = str(data.get("api_key") or reference)
    plan = str(data.get("plan") or "free").strip().casefold()
    units = as_int(data.get("tokens"), 0)
    if units < 0:
        return fail("tokens must be zero or positive", error_kind="validation_error",
                    rejected_field="tokens")

    plans = _plan_table()
    if not plans:
        return fail("billing block declares no plan table", error_kind="block_refused")
    plan_known = plan in plans

    usage = execute(
        "billing",
        {
            "api_key": owner,
            "block": str(data.get("block_used") or "delivery"),
            "tokens": units,
        },
        action=BLOCK_DEFAULT_ACTIONS.get("billing"),
    )
    if block_failed(usage):
        return fail(refusal_text(usage))

    limit = _limit(plan, plans) if plan_known else None
    return ok({
        "reference": reference,
        "status": str(data.get("status") or "open"),
        "notes": str(data.get("notes") or ""),
        "owner": owner,
        "block_used": data.get("block_used") or "delivery",
        "plan": plan,
        "plan_known": plan_known,
        "tokens": units,
        "recorded": bool(usage.get("recorded")),
        "cost_cents": usage.get("cost_cents", 0),
        "quota_limit": limit,
        "quota_used": units,
        "quota_exhausted": None if limit is None else units >= int(limit),
        "quota_basis": (
            "billing.PLANS[%s].requests" % plan if plan_known
            else "plan not declared by the block; no quota reported"
        ),
        "metered": units > 0,
        "authority": {"label": "certified", "layer": 5, "basis": "billing block PLANS + record_usage"},
    })
