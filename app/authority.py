"""Authority precedence as versioned data (precedence.v1).

Layers: 1 certified > 2 documents > 3 formulas > 4 procedures. The model is
told the winner; it never chooses. Every answer carries its layer label.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_KERNEL_LADDER = (
    Path(__file__).resolve().parent
    / "cerebrum_product_kernel"
    / "precedence_ladder.v1.json"
)

FALLBACK_LAYERS: List[Dict[str, Any]] = [
    {"rank": 1, "id": "certified", "label": "certified", "description": "Certified kernel definition"},
    {"rank": 2, "id": "documents", "label": "document", "description": "Uploaded source document"},
    {"rank": 3, "id": "formulas", "label": "formula", "description": "Computed formula"},
    {"rank": 4, "id": "procedures", "label": "procedure", "description": "Project procedure"},
]


def _ladder() -> List[Dict[str, Any]]:
    try:
        data = json.loads(_KERNEL_LADDER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return list(FALLBACK_LAYERS)
    layers = None
    if isinstance(data, dict):
        layers = data.get("layers") or data.get("rank")
    if not isinstance(layers, list) or not layers:
        return list(FALLBACK_LAYERS)
    out: List[Dict[str, Any]] = []
    for index, layer in enumerate(layers, start=1):
        if not isinstance(layer, dict):
            continue
        label = str(layer.get("label") or layer.get("name") or layer.get("id") or index)
        out.append(
            {
                "rank": int(layer.get("rank") or index),
                "id": str(layer.get("id") or layer.get("name") or label),
                "label": label,
                "description": str(layer.get("description") or ""),
            }
        )
    return out or list(FALLBACK_LAYERS)


LAYERS = _ladder()
PRECEDENCE_VERSION = "precedence.v1"


def layer(layer_id: str) -> Dict[str, Any] | None:
    for item in LAYERS:
        if item["id"] == layer_id or item["label"] == layer_id:
            return dict(item)
    return None


def label_for(layer_id: str) -> str:
    found = layer(layer_id)
    if found is None:
        return "unclassified"
    return "%s (layer %d, %s)" % (found["label"], found["rank"], PRECEDENCE_VERSION)


def resolve(candidates: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """The winner is the highest-authority candidate; the model never chooses."""
    ranked = []
    for candidate in candidates or []:
        found = layer(str(candidate.get("layer") or ""))
        if found is None:
            continue
        ranked.append((found["rank"], candidate))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0])
    return ranked[0][1]
