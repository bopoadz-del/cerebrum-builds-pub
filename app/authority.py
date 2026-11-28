"""Authority labels from the precedence ladder (precedence.v1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
LADDER = ROOT / "app" / "cerebrum_product_kernel" / "precedence_ladder.v1.json"


def ladder() -> List[Dict[str, Any]]:
    try:
        data = json.loads(LADDER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [
            {"layer": 1, "rank": 1, "label": "certified"},
            {"layer": 2, "rank": 2, "label": "documents"},
            {"layer": 3, "rank": 3, "label": "formulas"},
            {"layer": 4, "rank": 4, "label": "procedures"},
        ]
    return list(data.get("rank") or [])


def label_for_layer(layer: int) -> str:
    for item in ladder():
        if int(item.get("layer", 0)) == int(layer):
            return str(item.get("label") or "")
    return "unknown"


def answer_label(layer: int, basis: str) -> Dict[str, Any]:
    return {"label": label_for_layer(layer), "layer": int(layer), "basis": str(basis)}
