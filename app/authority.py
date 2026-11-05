"""Authority labels for every answer (precedence.v1).

Layer 1 certified beats layer 2 documents beats layer 3 formulas beats layer 4
procedures. The label travels with the answer; the caller never has to guess
which layer produced a number.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LADDER_PATH = ROOT / "app" / "cerebrum_product_kernel" / "precedence_ladder.v1.json"

LAYERS = {
    1: "certified",
    2: "documents",
    3: "formulas",
    4: "procedures",
}

SOURCE_LAYER = {
    "contract": 2,
    "boq": 2,
    "source_of_record": 2,
    "kernel_formula": 3,
    "formula": 3,
    "block": 4,
}


def ladder() -> dict:
    try:
        return json.loads(LADDER_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"layers": [{"rank": rank, "label": label} for rank, label in LAYERS.items()]}


def authority_label(source: str, layer: int | None = None, detail: str = "") -> dict:
    rank = int(layer or SOURCE_LAYER.get(str(source), 4))
    label = LAYERS.get(rank, "procedures")
    return {
        "layer": rank,
        "label": label,
        "source": str(source),
        "detail": str(detail or source),
        "precedence": "precedence.v1",
    }


def winner(candidates):
    """The highest-authority candidate; divergence is reported, not hidden."""
    ranked = sorted(
        [c for c in candidates if isinstance(c, dict)],
        key=lambda item: int(item.get("layer") or 4),
    )
    if not ranked:
        return None, []
    best = ranked[0]
    divergent = [c for c in ranked[1:] if c.get("value") != best.get("value")]
    return best, divergent
