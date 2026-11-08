"""The authority layers, as versioned data (precedence.v1).

Every answer carries the layer it came from so an operator can see whether a
figure is certified, read from the documents, computed by a formula, or a
procedure. The ladder is loaded from the kernel's versioned JSON; this module
names no precedence of its own.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.cerebrum_product_kernel import precedence

PRECEDENCE_VERSION = precedence.PRECEDENCE_VERSION


def ladder() -> Dict[int, int]:
    return precedence.load_ladder()


def layer_name(layer: int) -> str:
    return precedence.LAYER_LABELS.get(int(layer), "documents")


def label(layer: int, source: str) -> Dict[str, Any]:
    """The authority label an answer carries."""
    return {
        "layer": int(layer),
        "name": layer_name(layer),
        "source": str(source),
        "precedence": PRECEDENCE_VERSION,
    }


def precedence_table() -> Dict[str, Any]:
    rank = ladder()
    return {
        "schema": PRECEDENCE_VERSION,
        "layers": [
            {"layer": layer, "rank": rank.get(layer), "name": layer_name(layer)}
            for layer in sorted(rank)
        ],
        "rule": "a higher layer wins; the model is told the winner, never asked to choose",
    }


def divergence(winner: Dict[str, Any], loser: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    """A record of what the losing layer would have said."""
    if not loser:
        return []
    return [
        {
            "rule": PRECEDENCE_VERSION + ".shadow",
            "winner": dict(winner),
            "loser": dict(loser),
        }
    ]
