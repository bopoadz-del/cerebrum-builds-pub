"""The four-layer authority ladder, as data, for every answer this product gives.

Layer 1 certified > layer 2 documents > layer 3 formulas > layer 4
procedures. The rank table is the kernel's versioned ``precedence.v1``
file; this module is the product-facing seam over it so a capability can
label an answer with the layer that produced it without re-implementing
the ordering.

Sources of record for this project are layer 2: the uploaded contract
excerpt and BOQ. A contract clause outranks a formula, which outranks a
local procedure -- the model is told the winner, it never chooses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.cerebrum_product_kernel.precedence import (
    LAYER_LABELS,
    PRECEDENCE_VERSION,
    load_ladder,
)

CONTRACT_SOURCE = "document:73bb6fb4f55541d4ac99427be77c8471_harbourline_contract.pdf"
BOQ_SOURCE = "document:a903d4ccba764b6f84b39e65b8b6add3_harbourline_boq.xlsx"

DOCUMENTS = (CONTRACT_SOURCE, BOQ_SOURCE)


@dataclass(frozen=True)
class Claim:
    """One candidate answer and the layer that produced it."""

    layer: int
    value: Any
    source: str = ""


def label(layer: int) -> str:
    """``"2:documents"`` -- the label every answer carries."""
    if int(layer) not in LAYER_LABELS:
        raise ValueError(f"unknown precedence layer: {layer}")
    return f"{int(layer)}:{LAYER_LABELS[int(layer)]}"


def ladder() -> Dict[int, int]:
    return load_ladder()


def resolve(claims: Iterable[Claim]) -> Dict[str, Any]:
    """The winning claim plus every losing claim as a divergence record.

    A tie inside one layer is resolved by the source name, never by the
    model: two documents that disagree are reported as divergent, and the
    answer still names the winner it used.
    """
    ranked = sorted(
        (Claim(int(c.layer), c.value, str(c.source or "")) for c in claims),
        key=lambda c: (ladder().get(c.layer, c.layer), c.source),
        reverse=True,
    )
    if not ranked:
        return {"winner": None, "authority": None, "divergences": [], "precedence": PRECEDENCE_VERSION}
    winner = ranked[0]
    divergences: List[Dict[str, Any]] = [
        {
            "layer": c.layer,
            "label": label(c.layer),
            "source": c.source,
            "value": c.value,
        }
        for c in ranked[1:]
        if c.value != winner.value
    ]
    return {
        "winner": winner.value,
        "authority": label(winner.layer),
        "source": winner.source,
        "divergences": divergences,
        "precedence": PRECEDENCE_VERSION,
    }


def document_claim(value: Any, source: Optional[str] = None) -> Claim:
    """A value taken from the uploaded documents (layer 2)."""
    return Claim(2, value, source or CONTRACT_SOURCE)
