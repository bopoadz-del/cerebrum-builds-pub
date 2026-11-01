"""precedence.v1 -- the layer an answer came from, as versioned data.

The authority ladder is fixed and never chosen by a model:

    1 certified > 2 documents > 3 formulas > 4 procedures

Every answer this platform returns carries a label naming the layer, the
layer's name and the source that produced it, so an operator can see which
layer answered. ``authority`` is the one place that decides the ladder;
routes and the console read the label from here rather than inventing one.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SCHEMA = "precedence.v1"

#: The ladder, highest first. Layer numbers are the contract; names are for
#: the operator.
LAYERS: List[Dict[str, Any]] = [
    {"layer": 1, "name": "certified", "description": "signed, certified capability output"},
    {"layer": 2, "name": "documents", "description": "the customer's own ingested sources"},
    {"layer": 3, "name": "formulas", "description": "the platform's deterministic formulas and blocks"},
    {"layer": 4, "name": "procedures", "description": "operator-configured procedure settings"},
]

_BY_NAME = {item["name"]: item for item in LAYERS}


def layer(name: str) -> Dict[str, Any]:
    """The ladder entry for a layer name. An unknown name is layer 4."""
    item = _BY_NAME.get(str(name))
    if item is None:
        item = LAYERS[-1]
    return dict(item)


def label(name: str, source: str, *, detail: Optional[str] = None) -> Dict[str, Any]:
    """One answer's authority label: layer, name, source (+ optional detail)."""
    out = layer(name)
    out["source"] = str(source)
    out["schema"] = SCHEMA
    if detail:
        out["detail"] = str(detail)
    return out


def precedence_table() -> Dict[str, Any]:
    """The whole ladder as data, for GET /v1/authority."""
    return {
        "schema": SCHEMA,
        "order": [item["name"] for item in LAYERS],
        "rule": "1 certified > 2 documents > 3 formulas > 4 procedures",
        "divergence": (
            "when two layers disagree the higher layer wins and the lower "
            "layer's answer is recorded as a divergence, never silently dropped"
        ),
        "layers": [dict(item) for item in LAYERS],
    }
