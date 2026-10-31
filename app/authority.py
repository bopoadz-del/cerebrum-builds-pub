"""Authority labels from the declared precedence ladder.

Layers: 1 certified > 2 documents > 3 formulas > 4 procedures. The label
travels with every answer so an operator sees which layer it came from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_LADDER = Path(__file__).resolve().parents[1] / "app" / "cerebrum_product_kernel" / "precedence_ladder.v1.json"

_FALLBACK = {
    1: "certified",
    2: "documents",
    3: "formulas",
    4: "procedures",
}


def _ladder() -> Dict[str, Any]:
    try:
        return json.loads(_LADDER.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def label_for(layer: int) -> str:
    ladder = _ladder()
    for row in ladder.get("rank") or ladder.get("layers") or ladder.get("precedence") or []:
        if isinstance(row, dict) and int(row.get("layer", 0)) == int(layer):
            return str(row.get("label") or row.get("name") or _FALLBACK.get(layer, "documents"))
    return _FALLBACK.get(int(layer), "documents")


def authority(layer: int = 2, source: str = "") -> Dict[str, Any]:
    return {
        "layer": int(layer),
        "label": label_for(layer),
        "source": source,
        "precedence": "1 certified > 2 documents > 3 formulas > 4 procedures",
    }
