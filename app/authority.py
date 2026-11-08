"""The four-layer authority ladder, as versioned data.

1 certified > 2 documents > 3 formulas > 4 procedures. The ladder is read from
``app/cerebrum_product_kernel/precedence_ladder.v1.json`` at use time; it is
never typed into a prompt or decided by a model. A resolution returns the
winner plus a divergence record naming the layers that disagreed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LADDER_FILE = ROOT / "app" / "cerebrum_product_kernel" / "precedence_ladder.v1.json"

_DEFAULT = {1: "certified", 2: "documents", 3: "formulas", 4: "procedures"}


def load_ladder() -> Dict[int, Dict[str, Any]]:
    try:
        data = json.loads(LADDER_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {layer: {"layer": layer, "rank": layer, "label": label} for layer, label in _DEFAULT.items()}
    out: Dict[int, Dict[str, Any]] = {}
    for row in data.get("rank") or []:
        try:
            layer = int(row.get("layer"))
        except (TypeError, ValueError):
            continue
        out[layer] = {
            "layer": layer,
            "rank": int(row.get("rank") or layer),
            "label": str(row.get("label") or _DEFAULT.get(layer, "")),
        }
    return out or {layer: {"layer": layer, "rank": layer, "label": label} for layer, label in _DEFAULT.items()}


def ladder() -> Dict[int, int]:
    return {layer: int(row["rank"]) for layer, row in load_ladder().items()}


def layer_label(layer: int) -> str:
    row = load_ladder().get(int(layer))
    return str(row["label"]) if row else ""


def label(layer: int) -> str:
    name = layer_label(layer)
    return f"layer {int(layer)} {name}" if name else f"layer {int(layer)}"


def resolve(candidates: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Pick the highest-authority candidate and record who disagreed.

    Each candidate carries ``layer`` and ``value``. A higher layer number is
    LOWER authority (procedures lose to certified documents), so the winner is
    the smallest rank.
    """
    ranks = ladder()
    rows = [dict(candidate) for candidate in candidates]
    if not rows:
        return {"winner": None, "divergences": [], "rule": "precedence.v1.ladder"}
    for row in rows:
        row["rank"] = ranks.get(int(row.get("layer") or 4), int(row.get("layer") or 4))
    rows.sort(key=lambda row: row["rank"])
    winner = rows[0]
    divergences = [
        {
            "rule": "precedence.v1.ladder",
            "winner": winner.get("value"),
            "loser": row.get("value"),
            "winner_layer": winner.get("layer"),
            "loser_layer": row.get("layer"),
        }
        for row in rows[1:]
        if row.get("value") != winner.get("value")
    ]
    return {"winner": winner.get("value"), "winning_layer": winner.get("layer"), "divergences": divergences, "rule": "precedence.v1.ladder"}
