"""Kernel formula access plus this product's declared improvised formulas.

The platform evaluates the certified universal definitions by address.  No
rate or threshold is encoded here: every value is a named input the caller
supplies, and a missing input fails closed.

IMPROVISED, NO STORE COVERAGE: the slot algebra in
``writer_definitions.jsonl`` (``delivery:slot_count_v1`` and
``delivery:slot_open_capacity_v1``) is authored by the writer because neither
the kernel nor the Store publishes a calendar/slot definition.  It is
labelled as improvised everywhere it is shown, and its provenance is recorded
in ``docs/provenance/provenance.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.cerebrum_product_kernel.formulas.evaluator import MissingInput, safe_eval

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
DEFINITIONS_FILE = ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"
WRITER_FILE = PACKAGE / "writer_definitions.jsonl"

IMPROVISED_LABEL = "improvised, no Store coverage"


def _kernel_definitions() -> List[Dict[str, Any]]:
    try:
        data = json.loads(DEFINITIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(data.get("definitions") or [])


def _writer_definitions() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        lines = WRITER_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            out.append({**row, "key": row["id"], "label": IMPROVISED_LABEL})
    return out


def definitions() -> List[Dict[str, Any]]:
    return _kernel_definitions() + _writer_definitions()


def by_key(key: str) -> Dict[str, Any] | None:
    for item in definitions():
        if str(item.get("key")) == str(key):
            return item
    return None


def evaluate(key: str, variables: Dict[str, Any]) -> float:
    definition = by_key(key)
    if definition is None:
        raise KeyError("no kernel definition at %s" % key)
    grounded: Dict[str, float] = {}
    for name in definition.get("inputs") or []:
        if name not in variables or variables[name] is None:
            raise MissingInput(name)
        grounded[str(name)] = float(variables[name])
    return float(safe_eval(str(definition.get("expression") or "0"), grounded))


def authority(key: str) -> Dict[str, Any]:
    definition = by_key(key) or {}
    improvised = str(definition.get("label") or "") == IMPROVISED_LABEL
    return {
        "label": IMPROVISED_LABEL if improvised else "certified",
        "layer": None if improvised else 1,
        "basis": key,
        "source": definition.get("source") if improvised else "kernel",
    }


def catalogue() -> List[Dict[str, Any]]:
    out = []
    for item in definitions():
        improvised = str(item.get("label") or "") == IMPROVISED_LABEL
        out.append({
            "key": item.get("key"),
            "name": item.get("name"),
            "inputs": list(item.get("inputs") or []),
            "expression": item.get("expression"),
            "output": item.get("output"),
            "authority": authority(str(item.get("key"))),
        })
    return out
