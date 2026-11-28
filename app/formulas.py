"""Kernel formula access.

The platform evaluates the certified universal definitions by address.  No
rate or threshold is encoded here: every value is a named input the caller
supplies, and a missing input fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.cerebrum_product_kernel.formulas.evaluator import MissingInput, safe_eval

ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS_FILE = ROOT / "app" / "cerebrum_product_kernel" / "formulas" / "universal_definitions.json"


def definitions() -> List[Dict[str, Any]]:
    try:
        data = json.loads(DEFINITIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(data.get("definitions") or [])


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


def catalogue() -> List[Dict[str, Any]]:
    return [
        {
            "key": item.get("key"),
            "name": item.get("name"),
            "inputs": list(item.get("inputs") or []),
            "expression": item.get("expression"),
            "output": item.get("output"),
            "authority": {"label": "certified", "layer": 1, "basis": item.get("key")},
        }
        for item in definitions()
    ]
