"""Customer invoicing and subcontractor payout lifecycle.

The vendored payment_escrow block owns the exact escrow math (hold, fee
quote, release, partial release, refund).  Country and currency were NOT
declared by the customer, so they are read at run time from app.money_settings:
with either unset the quote is reported as withheld and the operator is told
which setting to supply -- never a guessed country or currency.  Tax is the
kernel's tax_amount definition over the operator's tax rate.

SCALE: one payment lifecycle step per call.
READS: caller fields; PLATFORM_CURRENCY, PLATFORM_RATE_PLATFORM_FEE and
       PLATFORM_TAX_RATE from app.money_settings.
WRITES: the escrow outcome in the response; the route persists the record.
NEVER: an assumed currency, a typed fee rate, or a typed tax rate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import domain_rules, formulas, money_settings
from app.action_common import as_float, block_failed, fail, ok, refusal_text
from app.dispatch import execute_sequence

CAPABILITY_ID = "invoicing_and_payouts"
ENTITY = "invoicing_and_payouts"
BLOCK_IDS = ["payment_escrow"]
BLOCK_DEFAULT_ACTIONS = {"payment_escrow": "status"}
AUTHORED_BY = "codewhale exec"

STAGES = ("hold", "fee_quote", "release", "partial_release", "refund")


def _currency() -> Optional[str]:
    try:
        return money_settings.currency()
    except money_settings.MoneySettingMissing:
        return None


def _fee_rate() -> Optional[float]:
    try:
        return money_settings.rate("platform_fee")
    except (money_settings.MoneySettingMissing, ValueError):
        return None


def _tax_rate() -> Optional[float]:
    try:
        return money_settings.tax_rate()
    except (money_settings.MoneySettingMissing, ValueError):
        return None


def _tax(amount: float) -> Dict[str, Any]:
    rate = _tax_rate()
    if rate is None:
        return {"tax": "withheld", "tax_rate": None, "setting": "PLATFORM_TAX_RATE",
                "authority": None}
    value = formulas.evaluate(
        "universal:tax_amount_v1", {"net_amount": amount, "tax_rate": rate}
    )
    return {
        "tax": round(value, 2),
        "tax_rate": rate,
        "setting": None,
        "authority": {"label": "certified", "layer": 1, "basis": "universal:tax_amount_v1"},
    }


def _lifecycle() -> List[Dict[str, Any]]:
    return [{"stage": stage, "implemented": True} for stage in STAGES]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "invoice")
    booking = str(data.get("booking_reference") or reference)
    invoice = str(data.get("invoice_reference") or booking)
    payment_id = invoice or booking
    amount = as_float(data.get("amount"))
    stage = str(data.get("payout_stage") or "hold").strip().casefold()
    if stage not in STAGES:
        return fail("payout_stage must be one of %s" % (list(STAGES),),
                    error_kind="validation_error", rejected_field="payout_stage",
                    allowed_values=list(STAGES))
    currency = _currency()

    if amount is None or amount <= 0:
        return ok({
            "booking_reference": booking,
            "invoice_reference": invoice,
            "payout_stage": stage,
            "state": "no_amount",
            "amount": amount,
            "currency": currency if currency else "withheld",
            "currency_setting": None if currency else "PLATFORM_CURRENCY",
            "quote": "withheld",
            "lifecycle": _lifecycle(),
            "invoice_digest": domain_rules.canonical_digest(
                {"invoice": invoice, "amount": amount, "stage": stage}
            ),
            "reason": "no positive amount to invoice",
        })

    rate = _fee_rate()
    if currency is None or rate is None:
        # The block is still exercised, but its numbers are not reported:
        # pricing a customer's money on a currency or a fee nobody declared
        # would be a guess.
        execute_sequence(
            "payment_escrow",
            [{"action": "fee_quote", "input": {"amount": amount}}],
        )
        missing = "PLATFORM_CURRENCY" if currency is None else "PLATFORM_RATE_PLATFORM_FEE"
        return ok({
            "booking_reference": booking,
            "invoice_reference": invoice,
            "payout_stage": stage,
            "state": "awaiting_setting",
            "amount": amount,
            "currency": currency if currency else "withheld",
            "currency_setting": None if currency else "PLATFORM_CURRENCY",
            "quote": "withheld",
            "setting": missing,
            "lifecycle": _lifecycle(),
            "invoice_digest": domain_rules.canonical_digest(
                {"invoice": invoice, "amount": amount, "stage": stage}
            ),
        })

    config = {
        "platform_fee_rate": str(rate),
        "platform_fee_fixed": "0.00",
        "currency": currency,
    }
    steps: List[Dict[str, Any]] = []
    if stage == "fee_quote":
        steps.append({"action": "fee_quote", "input": {"amount": amount}})
    elif stage == "hold":
        steps.append({"action": "hold", "input": {"payment_id": payment_id, "amount": amount}})
    elif stage == "release":
        steps.append({"action": "hold", "input": {"payment_id": payment_id, "amount": amount}})
        steps.append({"action": "release", "input": {"payment_id": payment_id}})
    elif stage == "partial_release":
        partial = as_float(data.get("released_amount"))
        if partial is None or partial <= 0 or partial > amount:
            return fail("released_amount must be between 0 and amount",
                        error_kind="validation_error", rejected_field="released_amount")
        steps.append({"action": "hold", "input": {"payment_id": payment_id, "amount": amount}})
        steps.append({"action": "partial_release",
                      "input": {"payment_id": payment_id, "amount": partial}})
    elif stage == "refund":
        steps.append({"action": "hold", "input": {"payment_id": payment_id, "amount": amount}})
        steps.append({"action": "refund", "input": {"payment_id": payment_id}})

    escrow = execute_sequence("payment_escrow", steps, config=config)
    if block_failed(escrow):
        return fail(refusal_text(escrow))

    tax = _tax(amount)
    return ok({
        "booking_reference": booking,
        "invoice_reference": invoice,
        "payout_stage": stage,
        "state": escrow.get("state"),
        "amount": amount,
        "currency": currency,
        "platform_fee": escrow.get("platform_fee"),
        "provider_net": escrow.get("provider_net"),
        "released_amount": escrow.get("released_amount"),
        "refunded_amount": escrow.get("refunded_amount"),
        "tax": tax["tax"],
        "tax_rate": tax["tax_rate"],
        "tax_setting": tax["setting"],
        "lifecycle": _lifecycle(),
        "invoice_digest": domain_rules.canonical_digest(
            {"invoice": invoice, "amount": amount, "stage": stage}
        ),
        "authority": tax["authority"],
    })
