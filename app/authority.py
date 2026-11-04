"""Authority labels every answer carries.

The four-layer ladder (certified / documents / formulas / procedures) is the
kernel's versioned data, not a second copy here: this module only names the
layers for a response so an operator can see which layer answered.
"""

from __future__ import annotations

from typing import Any, Dict

from app.cerebrum_product_kernel.precedence import (
    LAYER_LABELS,
    PRECEDENCE_VERSION,
    load_ladder,
)

#: Reverse map: the kernel's label -> its layer number.
LAYER_BY_LABEL = {label: layer for layer, label in LAYER_LABELS.items()}


def layer_of(name: Any) -> Dict[str, Any]:
    """The layer record for a name, an int layer, or an unknown name."""
    if isinstance(name, int) and name in LAYER_LABELS:
        return {"layer": name, "name": LAYER_LABELS[name], "label": LAYER_LABELS[name]}
    text = str(name or "").strip().lower()
    for layer, label in LAYER_LABELS.items():
        if text in (label, label + "s"):
            return {"layer": layer, "name": label, "label": label}
    return {"layer": 0, "name": text or "unknown", "label": text or "unknown"}


def label(name: Any) -> Dict[str, Any]:
    layer = layer_of(name)
    return {
        "layer": layer["layer"],
        "name": layer["name"],
        "label": layer["label"],
        "policy": PRECEDENCE_VERSION,
    }


def ladder() -> Dict[str, Any]:
    return {
        "policy": PRECEDENCE_VERSION,
        "ranks": load_ladder(),
        "layers": [label(layer) for layer in sorted(LAYER_LABELS)],
    }
