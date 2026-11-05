"""Authority: which source wins, recorded on every answer.

Layers, highest first: 1 certified > 2 documents > 3 formulas > 4
procedures. The winner is decided from versioned data (precedence.v1 below),
never by a model choosing; every answer carries the winning layer's label and
the divergences the lower layers would have produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PRECEDENCE_PATH = ROOT / "app" / "cerebrum_product_kernel" / "precedence_ladder.v1.json"

PRECEDENCE_V1: Dict[str, Any] = {
    "version": "precedence.v1",
    "order": [
        {"layer": 1, "name": "certified", "label": "L1 certified"},
        {"layer": 2, "name": "documents", "label": "L2 documents"},
        {"layer": 3, "name": "formulas", "label": "L3 formulas"},
        {"layer": 4, "name": "procedures", "label": "L4 procedures"},
    ],
}

_LABELS = {row["name"]: row["label"] for row in PRECEDENCE_V1["order"]}
_RANK = {row["name"]: row["layer"] for row in PRECEDENCE_V1["order"]}


def _normalise(data: Dict[str, Any]) -> Dict[str, Any]:
    """Read either the kernel's {"rank": [...]} ladder or our {"order": []}."""
    rows = data.get("order") or data.get("rank") or []
    order = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("label") or "")
        layer = row.get("layer", row.get("rank"))
        if not name or layer is None:
            continue
        order.append({"layer": int(layer), "name": name, "label": f"L{int(layer)} {name}"})
    if not order:
        return PRECEDENCE_V1
    return {
        "version": str(data.get("schema") or data.get("version") or "precedence.v1"),
        "order": sorted(order, key=lambda row: row["layer"]),
    }


def ladder() -> Dict[str, Any]:
    if PRECEDENCE_PATH.is_file():
        try:
            data = json.loads(PRECEDENCE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _normalise(data)
        except (OSError, ValueError):
            pass
    return PRECEDENCE_V1


def label(layer: str) -> str:
    for row in ladder().get("order", []):
        if row.get("name") == layer:
            return str(row.get("label") or layer)
    return str(layer)


def rank(layer: str) -> int:
    for row in ladder().get("order", []):
        if row.get("name") == layer:
            return int(row.get("layer") or 99)
    return 99


def decide(claims: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Pick the highest-authority claim; record what the others said.

    Each claim is {"layer": ..., "source": ..., "value": ..., "text": ...}.
    """
    rows = [dict(c) for c in claims if isinstance(c, dict) and c.get("layer")]
    if not rows:
        return {"winner": None, "label": None, "divergences": [], "precedence": ladder().get("version")}
    rows.sort(key=lambda row: rank(str(row["layer"])))
    winner = rows[0]
    divergences = [
        {
            "layer": row.get("layer"),
            "label": label(str(row.get("layer"))),
            "source": row.get("source"),
            "value": row.get("value"),
        }
        for row in rows[1:]
    ]
    return {
        "winner": winner,
        "label": label(str(winner["layer"])),
        "divergences": divergences,
        "precedence": ladder().get("version"),
    }


def stamp(result: Dict[str, Any], layer: str, source: str, divergences: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Attach the authority label an operator reads on every answer."""
    out = dict(result)
    out["authority"] = {
        "layer": layer,
        "label": label(layer),
        "source": source,
        "precedence": ladder().get("version"),
        "divergences": divergences or [],
    }
    return out
