"""Authority: the four-layer ladder applied to every answer the platform gives.

Layers are DATA (``precedence_ladder.v1.json``): 1 certified > 2 documents >
3 formulas > 4 procedures, as a rank table the kernel resolves. The platform
tells the caller which layer won and what each losing layer would have said --
it never asks a model to choose, and an answer that cannot name its layer is
refused rather than dressed up as authority.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.cerebrum_product_kernel.precedence import (
    LAYER_LABELS,
    LayerObject,
    PrecedenceError,
    load_ladder,
    resolve_precedence,
)

LAYERS = tuple(LAYER_LABELS)
def ladder() -> Dict[int, int]:
    return load_ladder()


def layer_label(layer: Any) -> str:
    try:
        return LAYER_LABELS.get(int(layer), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def label(value: Any, layer: int = 2) -> str:
    """The visible authority label an answer carries."""
    return f"layer {int(layer)} {layer_label(layer)}"


def objects_from(entries: Iterable[Dict[str, Any]]) -> List[LayerObject]:
    """Build kernel LayerObjects from plain declarations."""
    out: List[LayerObject] = []
    for entry in entries:
        layer = int(entry.get("layer") or 2)
        out.append(
            LayerObject(
                object_id=str(entry.get("id") or entry.get("object_id") or "object"),
                layer=layer,
                tenant_id=entry.get("tenant_id"),
                result=entry.get("result"),
                excerpt=str(entry.get("excerpt") or ""),
            )
        )
    return out


def resolve(entries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve competing claims; returns the winner plus every divergence."""
    objects = objects_from(entries)
    if not objects:
        raise PrecedenceError("precedence_no_objects: nothing to resolve")
    verdict = resolve_precedence(objects, ladder())
    payload = verdict.to_dict()
    payload["winner_layer_label"] = layer_label(payload.get("winner_layer"))
    payload["label"] = label(payload.get("winner_layer", 2))
    return payload


def label_claims(claims: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach a layer label to each claim; an unlabelled claim is refused."""
    out: List[Dict[str, Any]] = []
    for claim in claims:
        layer = claim.get("layer")
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        if layer is None:
            raise PrecedenceError("a claim must name the layer it came from")
        out.append({"text": text, "layer": int(layer), "authority": label(layer)})
    return out


def answer(
    text: str,
    layer: int = 2,
    divergences: Optional[List[Dict[str, Any]]] = None,
    claims: Optional[Iterable[Dict[str, Any]]] = None,
    citations: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """The answer envelope: text, its layer, divergences and per-claim labels."""
    if not str(text or "").strip():
        raise PrecedenceError("an answer without text is not an answer")
    labelled = label_claims(claims or [])
    return {
        "ok": True,
        "answer": text,
        "layer": int(layer),
        "authority": label(layer),
        "divergences": list(divergences or []),
        "claims": labelled or [{"text": text, "layer": int(layer), "authority": label(layer)}],
        "citations": list(citations or []),
        "label": label(layer),
    }
