"""Formula sources, in resolution order: kernel, Store, then improvised.

Every figure this platform computes is evaluated from a definition, never
typed into a handler.  The kernel's base set is resolved together with this
platform's domain extensions (``writer_definitions.jsonl``), so each answer
carries the address of the definition that produced it:

    kernel      universal:late_fee_simple_v1   (delay damages, day count)
    kernel      universal:discount_amount_v1   (a rate applied to an amount)
    extension   contracts:boq_line_amount_v1   (quantity x rate)
    extension   contracts:ipc_net_certified_v1 (certificate net of retention)

The two extensions are the identities this contract states that no kernel
definition names; their rows cite the uploaded documents, and each one is also
appended to ``new_domain_candidates.jsonl`` for Store intake.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable

from app.cerebrum_product_kernel.formulas import load_base_definitions, resolve_definitions
from app.cerebrum_product_kernel.formulas.evaluator import safe_eval

HERE = Path(__file__).resolve().parent
WRITER_DEFINITIONS = HERE / "writer_definitions.jsonl"
CANDIDATES = HERE / "new_domain_candidates.jsonl"

#: The definition ids this platform computes with, by name.
BOQ_LINE_AMOUNT = "boq_line_amount"
IPC_NET_CERTIFIED = "ipc_net_certified"
RATE_APPLIED = "discount_amount"
LATE_FEE = "late_fee_simple"

#: Day-count convention for a per-day contractual rate expressed per annum.
DAYS_IN_YEAR = 365


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


@lru_cache(maxsize=1)
def definitions():
    """Kernel base set resolved with this platform's extensions."""
    overlay = {
        "set_id": "contracts",
        "tier": "domain-extension",
        "name": "Harbourline Civil Works contract arithmetic",
        "definitions": list(_read_jsonl(WRITER_DEFINITIONS)),
    }
    return resolve_definitions(load_base_definitions(), [overlay])


def definition(ident: str) -> Dict[str, Any]:
    resolved = definitions().get(str(ident))
    if resolved is None:
        raise KeyError("no definition %r in the resolved set" % ident)
    return dict(resolved)


def address(ident: str) -> str:
    return str(definition(ident).get("address") or ident)


def evaluate(ident: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one definition over its named inputs.

    Returns the value, the definition's address and the definition itself, so
    an answer can always say which layer produced its number.
    """
    entry = definition(ident)
    expression = str(entry.get("expression") or "")
    numbers: Dict[str, float] = {}
    for name in entry.get("inputs") or []:
        if name not in values:
            raise KeyError("%s needs input %r" % (ident, name))
        numbers[name] = float(values[name])
    value = safe_eval(expression, numbers)
    return {
        "value": value,
        "address": entry.get("address") or ident,
        "definition": ident,
        "expression": expression,
        "inputs": numbers,
        "tier": entry.get("tier"),
    }


def boq_line_amount(measured_quantity: Any, boq_rate: Any) -> Dict[str, Any]:
    return evaluate(BOQ_LINE_AMOUNT, {
        "measured_quantity": measured_quantity,
        "boq_rate": boq_rate,
    })


def net_certified(gross_certified: Any, retention_held: Any) -> Dict[str, Any]:
    return evaluate(IPC_NET_CERTIFIED, {
        "gross_certified": gross_certified,
        "retention_held": retention_held,
    })


def rate_applied(amount: Any, rate: Any) -> Dict[str, Any]:
    return evaluate(RATE_APPLIED, {"list_price": amount, "discount_rate": rate})


def delay_damages(contract_amount: Any, daily_rate: Any, delay_days: Any) -> Dict[str, Any]:
    """Per-day damages under Clause 8.7 through the kernel's late-fee identity.

    The kernel takes an annual rate with the day-count convention as an input
    (a contract term, not a constant); the daily rate is therefore expressed
    over the contract's own day count, never re-derived by a literal here.
    """
    return evaluate(LATE_FEE, {
        "overdue_amount": contract_amount,
        "annual_rate": float(daily_rate) * DAYS_IN_YEAR,
        "days_overdue": delay_days,
        "days_in_year": DAYS_IN_YEAR,
    })


def catalogue() -> Dict[str, Any]:
    """Every definition this platform computes with, and its address."""
    wanted = [
        BOQ_LINE_AMOUNT,
        IPC_NET_CERTIFIED,
        RATE_APPLIED,
        LATE_FEE,
    ]
    rows = []
    resolved = definitions()
    for ident in wanted:
        entry = resolved.get(ident)
        if entry is None:
            continue
        rows.append({
            "id": ident,
            "address": entry.get("address"),
            "tier": entry.get("tier"),
            "expression": entry.get("expression"),
            "inputs": list(entry.get("inputs") or []),
        })
    return {"policy": "precedence.v1", "definitions": rows}
