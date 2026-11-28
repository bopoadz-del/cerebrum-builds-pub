"""Construct block inputs from a domain record.

Callers send the capability's own fields.  The keys a block needs -- topic,
sql/table, file paths, channel, steps -- are synthesized here, never demanded
from the caller.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.dispatch import LOCKED_PATHS

ROOT = Path(__file__).resolve().parents[1]


def _block_json(block_id: str) -> Dict[str, Any]:
    path = LOCKED_PATHS.get(str(block_id))
    if path is None:
        return {}
    candidate = path.parent / "block.json"
    try:
        return json.loads(candidate.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def default_block_action(block_id: str) -> Optional[str]:
    """The action the block's own contract declares as its default."""
    data = _block_json(block_id)
    for item in data.get("inputs") or []:
        if not isinstance(item, dict):
            continue
        if item.get("name") in ("action", "operation") and item.get("default") is not None:
            return str(item["default"])
    return None


def domain_scalars(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[str(key)] = value
        else:
            out[str(key)] = json.dumps(value, sort_keys=True, default=str)
    return out


def prepare_block_input(block_id: str, payload: Optional[Dict[str, Any]] = None,
                        action: Optional[str] = None) -> Dict[str, Any]:
    step_action = action if action is not None else default_block_action(block_id)
    return {
        "block": str(block_id),
        "action": step_action,
        "input": domain_scalars(payload),
    }


def prepared_event_step(topic: str, payload: Optional[Dict[str, Any]] = None,
                        message: str = "") -> Dict[str, Any]:
    """The prepared event_bus child every workflow step must carry."""
    refs = domain_scalars(payload)
    if "reference" not in refs:
        refs["reference"] = topic
    return {
        "block": "event_bus",
        "action": "publish",
        "input": {
            "topic": str(topic),
            "payload": refs,
            "message": str(message or topic),
            "channel": "mcp",
            "tool": "event_bus",
        },
    }


def attach_result(step: Dict[str, Any], result: Any) -> Dict[str, Any]:
    """Store the first prepared step's result where a workflow shim reads it."""
    step.setdefault("input", {})["result"] = result
    return step
