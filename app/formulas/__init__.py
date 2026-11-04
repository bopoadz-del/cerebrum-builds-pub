"""Formula evaluation for the platform's numeric decisions.

Resolution order, per the brief: the Cerebrum kernel definition first (by
address, evaluated with the kernel's own safe evaluator -- never ``eval``);
then a Store formula; only then a formula written here, labelled
"improvised, no Store coverage" with its source cited, and appended to
``new_domain_candidates.jsonl`` through the kernel's candidate log.

A rate or threshold the customer owns is never a literal in an expression: it
is passed in as a named variable read from settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from app.cerebrum_product_kernel.formulas.evaluator import (
    MissingInput,
    UnsafeExpression,
    safe_eval,
)

HERE = Path(__file__).resolve().parent
UNIVERSAL_PATH = HERE.parent / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"
WRITER_DEFINITIONS_PATH = HERE / "writer_definitions.jsonl"
CANDIDATES_PATH = HERE / "new_domain_candidates.jsonl"

IMPROVISED = "improvised, no Store coverage"

#: Formulas this product needs that the kernel's universal table does not
#: carry. Each one is arithmetic over declared inputs, with its source cited.
WRITER_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "product:memo_criterion_total_v1": {
        "label": "Memo criterion total (five criteria, 0-20 each)",
        "expression": "c1 + c2 + c3 + c4 + c5",
        "source": "brief: memo_grading -- five criterion scores 0-20, banded total",
        "inputs": ["c1", "c2", "c3", "c4", "c5"],
    },
    "product:weighted_average_v1": {
        "label": "Programme weighted average (memos 60, defenses 20, capstone 20)",
        "expression": "memos * 0.6 + defenses * 0.2 + capstone * 0.2",
        "source": "brief: gradebook_and_transcript -- weighted 60/20/20",
        "inputs": ["memos", "defenses", "capstone"],
    },
    "product:graduation_average_v1": {
        "label": "Graduation headroom: weighted average above the mastery floor",
        "expression": "average - mastery_floor",
        "source": "brief: defenses_and_capstone -- graduation requires average >= 80",
        "inputs": ["average", "mastery_floor"],
    },
    "product:resit_deadline_days_v1": {
        "label": "Re-sit window after a failed term defense",
        "expression": "resit_days",
        "source": "brief: defenses_and_capstone -- re-sit scheduled within 7 days on fail",
        "inputs": ["resit_days"],
    },
    "product:session_minutes_total_v1": {
        "label": "Contact minutes in a 16-week track from the fixed session template",
        "expression": "weeks * (framework + case_prep + case_class + lab_1 + lab_2 + exam)",
        "source": "brief: enrolment_and_scheduling -- 16 weeks x 6 sessions from the fixed template",
        "inputs": ["weeks", "framework", "case_prep", "case_class", "lab_1", "lab_2", "exam"],
    },
}

_UNIVERSAL_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def universal_definitions() -> Dict[str, Dict[str, Any]]:
    global _UNIVERSAL_CACHE
    if _UNIVERSAL_CACHE is not None:
        return _UNIVERSAL_CACHE
    out: Dict[str, Dict[str, Any]] = {}
    try:
        raw = json.loads(UNIVERSAL_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    rows: Iterable[Any]
    if isinstance(raw, dict):
        rows = raw.get("definitions") or raw.get("formulas") or raw.values()
    else:
        rows = raw  # type: ignore[assignment]
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    _UNIVERSAL_CACHE = out
    return out


def definition_for(address: str) -> Dict[str, Any]:
    """The definition row for a kernel address or a writer formula id."""
    key = str(address or "").strip()
    universal = universal_definitions()
    if key in universal:
        return universal[key]
    qualified = key[len("universal:"):] if key.startswith("universal:") else key
    stems = {qualified, qualified[:-3] if qualified.endswith("_v1") else qualified + "_v1", key}
    for candidate, row in universal.items():
        short = candidate.split(":", 1)[-1]
        if short in stems or candidate == key:
            return row
    if key in WRITER_DEFINITIONS:
        return {"id": key, **WRITER_DEFINITIONS[key]}
    raise KeyError(f"unknown formula: {address}")


def evaluate(address: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a definition over named inputs. Missing inputs are refused."""
    row = definition_for(address)
    expression = str(row.get("expression") or "")
    if not expression:
        raise KeyError(f"formula {address!r} declares no expression")
    numeric: Dict[str, float] = {}
    for name, value in (variables or {}).items():
        if isinstance(value, bool):
            numeric[str(name)] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            numeric[str(name)] = float(value)
    try:
        value = safe_eval(expression, numeric)
    except MissingInput as exc:
        raise MissingInput(f"{address}: {exc}") from exc
    except UnsafeExpression as exc:
        raise UnsafeExpression(f"{address}: {exc}") from exc
    return {
        "id": row.get("id", address),
        "label": row.get("label", address),
        "expression": expression,
        "inputs": numeric,
        "value": value,
        "source": row.get("source", ""),
    }


def weighted_average(memos: float, defenses: float, capstone: float) -> Dict[str, Any]:
    return evaluate(
        "product:weighted_average_v1",
        {"memos": memos, "defenses": defenses, "capstone": capstone},
    )


def memo_total(criteria: Iterable[float]) -> Dict[str, Any]:
    values = list(criteria)[:5]
    while len(values) < 5:
        values.append(0.0)
    return evaluate(
        "product:memo_criterion_total_v1",
        {f"c{index + 1}": value for index, value in enumerate(values)},
    )


def band(total: float, pass_floor: float = 70.0, merit_floor: float = 80.0, distinction_floor: float = 90.0) -> str:
    """The band a memo total falls in; the floors are the operator's."""
    if total >= distinction_floor:
        return "distinction"
    if total >= merit_floor:
        return "merit"
    if total >= pass_floor:
        return "pass"
    return "resit"


def resit_required(total: float, pass_floor: float = 70.0) -> bool:
    return float(total) < float(pass_floor)


def _write_rows() -> None:
    """Persist the writer's formula rows and their domain candidates, once.

    Already shipped in the tree; a read-only image keeps them as they are.
    """
    try:
        _write_rows_unguarded()
    except OSError:
        return


def _write_rows_unguarded() -> None:
    if not WRITER_DEFINITIONS_PATH.is_file():
        lines = [
            json.dumps(
                {
                    "id": key,
                    "label": row["label"],
                    "source": f"{IMPROVISED}; {row['source']}",
                },
                sort_keys=True,
            )
            for key, row in WRITER_DEFINITIONS.items()
        ]
        WRITER_DEFINITIONS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    existing = set()
    if CANDIDATES_PATH.is_file():
        for line in CANDIDATES_PATH.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("definition"))
            except ValueError:
                continue
    rows = []
    for key in WRITER_DEFINITIONS:
        if key not in existing:
            rows.append(json.dumps({"definition": key}, sort_keys=True))
    if rows:
        with open(CANDIDATES_PATH, "a", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")


_write_rows()
