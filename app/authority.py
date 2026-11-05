"""Authority labels over the versioned precedence.v1 ladder.

The ladder is data (``app/cerebrum_product_kernel/precedence_ladder.v1.json``),
not prose: certified (1) > documents (2) > formulas (3) > procedures (4).
Every answer this platform returns carries the layer that produced it, and
a divergence record when more than one layer spoke.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.cerebrum_product_kernel.precedence import (
    LAYER_LABELS,
    PRECEDENCE_VERSION,
    LayerObject,
    default_ladder,
    load_ladder,
)

__all__ = [
    "authority_label",
    "resolve_objects",
    "PRECEDENCE_VERSION",
    "LAYER_LABELS",
]

_LAYER_SOURCE = {
    1: "certified_registry",
    2: "tenant_documents",
    3: "tenant_formulas",
    4: "tenant_procedures",
}


def authority_label(layer: int = 1, source: Optional[str] = None) -> Dict[str, Any]:
    level = int(layer)
    if level not in LAYER_LABELS:
        raise ValueError("unknown authority layer: %r" % (layer,))
    return {
        "schema": PRECEDENCE_VERSION,
        "layer": level,
        "label": LAYER_LABELS[level],
        "source": source or _LAYER_SOURCE[level],
    }


def resolve_objects(objects: Iterable[LayerObject], ladder: Optional[Dict[int, int]] = None):
    """Return (winner, divergence_records) using the shipped ladder."""
    rank = dict(ladder or load_ladder())
    candidates: List[LayerObject] = list(objects or [])
    if not candidates:
        return None, []
    winner = min(candidates, key=lambda item: rank.get(int(item.layer), 99))
    divergences = [
        {
            "rule": "precedence.v1.ladder",
            "winner": winner.object_id,
            "winner_layer": winner.layer,
            "loser": item.object_id,
            "loser_layer": item.layer,
            "loser_value": item.result if item.result is not None else item.excerpt,
        }
        for item in candidates
        if item is not winner
    ]
    return winner, divergences


def ladder() -> Dict[int, int]:
    return dict(default_ladder())
