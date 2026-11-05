"""Programme arithmetic.

Two registers, deliberately separated:

* a KERNEL definition, looked up by address from the shipped universal set
  (``universal:<id>_v<n>``) and evaluated with the kernel's own safe
  evaluator -- so a number the platform reports is the certified
  definition's number, and the answer carries the definition's tier;
* a WRITER definition, used only where no kernel or Store definition covers
  the arithmetic (rubric aggregation, rubric banding). Those are recorded in
  ``app/formulas/writer_definitions.jsonl`` with their source and listed as
  candidates, so nothing here is invented silently.

Every rate, threshold and weight a customer owns stays an argument: this
module holds the arithmetic, never the customer's numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.cerebrum_product_kernel.formulas import definition_index
from app.cerebrum_product_kernel.formulas.evaluator import MissingInput, safe_eval

HERE = Path(__file__).resolve().parent
WRITER_DEFINITIONS = HERE / "formulas" / "writer_definitions.jsonl"
CANDIDATES = HERE / "formulas" / "new_domain_candidates.jsonl"


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if result == result else float(default)


def definition(key: str) -> Optional[Dict[str, Any]]:
    """A kernel definition by address (``universal:<id>_v<n>``), or None.

    The kernel indexes definitions by id and carries the address alongside;
    both spellings resolve here so a caller can cite the address the
    precedence ladder uses.
    """
    wanted = str(key or "").strip()
    if not wanted:
        return None
    try:
        rows = definition_index()
    except Exception:
        return None
    for row in rows:
        if str(row.get("address") or "") == wanted:
            return row
    plain = wanted.split(":", 1)[-1]
    plain = plain.rsplit("_v", 1)[0] if "_v" in plain else plain
    for row in rows:
        if str(row.get("id") or "") in {wanted, plain}:
            return row
    return None


def kernel_value(key: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a kernel definition over supplied inputs.

    Returns ``{"ok", "value", "definition", "authority"}``. A missing input
    is a refusal, never a defaulted zero: the kernel's own evaluator raises
    MissingInput and the caller fails closed.
    """
    row = definition(key)
    if not row:
        return {"ok": False, "error": "no kernel definition at %s" % key, "error_kind": "undefined"}
    variables = {name: _num(value) for name, value in (inputs or {}).items()}
    try:
        value = safe_eval(str(row.get("expression") or ""), variables)
    except (MissingInput, ValueError, ZeroDivisionError) as exc:
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc), "error_kind": "missing_input"}
    return {
        "ok": True,
        "value": value,
        "definition": {
            "id": row.get("id"),
            "address": row.get("address"),
            "expression": row.get("expression"),
            "tier": row.get("tier"),
            "provenance": row.get("provenance") or {},
        },
        "authority": {"layer": 3, "label": "formula", "source": row.get("address")},
    }


def period_growth(prior: Any, current: Any) -> Dict[str, Any]:
    """Growth between two terms, through the kernel definition."""
    return kernel_value(
        "universal:period_over_period_growth_v1",
        {"prior_value": _num(prior), "current_value": _num(current)},
    )


def prorated(amount: Any, days_used: Any, days_in_period: Any) -> Dict[str, Any]:
    """A pro-rated amount, through the kernel definition."""
    return kernel_value(
        "universal:proration_v1",
        {
            "amount": _num(amount),
            "days_used": _num(days_used),
            "days_in_period": _num(days_in_period),
        },
    )


# ---------------------------------------------------------------------------
# WRITER definitions -- improvised, no Store coverage (see writer_definitions)
# ---------------------------------------------------------------------------
def weighted_average(values: Dict[str, Any], weights: Dict[str, Any]) -> float:
    """A weighted mean over named components.

    Row: ``writer:weighted_average_v1``. Weights are the customer's rubric
    weights; a component with no value yet contributes nothing and is not
    invented as a zero score (absence stays absence).
    """
    total_weight = 0.0
    total = 0.0
    for name, weight in (weights or {}).items():
        if name not in (values or {}) or values.get(name) is None:
            continue
        w = _num(weight)
        total += _num(values.get(name)) * w
        total_weight += w
    if total_weight <= 0:
        return 0.0
    return round(total / total_weight, 4)


def band_for(score: float, bands: Dict[str, Any]) -> str:
    """The band a score falls in, from the track's own band table.

    Row: ``writer:band_for_v1``. Highest band whose threshold is met wins;
    the lowest named band is the floor, so a score of 0 is still banded
    rather than silently unbanded.
    """
    value = _num(score)
    ordered = sorted(
        ((str(name), _num(threshold)) for name, threshold in (bands or {}).items()
         if str(name) != "rewrite_below"),
        key=lambda pair: pair[1],
        reverse=True,
    )
    for name, threshold in ordered:
        if value >= threshold:
            return name
    return ordered[-1][0] if ordered else ""


def rewrite_required(score: float, bands: Dict[str, Any]) -> bool:
    """Below the track's rewrite threshold the submission takes the rewrite
    path. The threshold is the customer's (rubric.bands.rewrite_below)."""
    threshold = _num((bands or {}).get("rewrite_below"), 70.0)
    return _num(score) < threshold


def criterion_ratio(met: float, total: float) -> float:
    """A bounded ratio used to turn evidence counts into a criterion score.

    Row: ``writer:criterion_ratio_v1``.
    """
    if _num(total) <= 0:
        return 0.0
    return round(min(1.0, max(0.0, _num(met) / _num(total))), 6)


def improvised_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in (WRITER_DEFINITIONS, CANDIDATES):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def kernel_roster() -> List[Dict[str, Any]]:
    """The kernel definitions this platform can reach, by address."""
    out = []
    for key in (
        "universal:period_over_period_growth_v1",
        "universal:proration_v1",
    ):
        row = definition(key)
        if row:
            out.append({"address": row.get("address"), "expression": row.get("expression"), "tier": row.get("tier")})
    return out


def describe() -> Dict[str, Any]:
    return {
        "kernel": kernel_roster(),
        "improvise": [row.get("id") for row in improvised_rows() if row.get("id")],
    }
