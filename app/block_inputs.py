"""Declared block actions and the one shaping step the runners share.

Each block's action is the block's own contract, recorded in
app.dispatch.BLOCK_DEFAULT_ACTIONS. ``prepare_block_input`` does only the
shaping a vendored block's own runtime requires: a workflow child carries
its operation and a ``result`` the Store shim reads, and an MCP notification
names the peer it drives. It never invents a domain value.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from app.dispatch import BLOCK_DEFAULT_ACTIONS


def default_block_action(block_id: str, default_actions: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if isinstance(default_actions, dict):
        value = default_actions.get(block_id)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = BLOCK_DEFAULT_ACTIONS.get(str(block_id or "").strip())
    return value if value else None


def prepare_block_input(
    block_id: str,
    record: Dict[str, Any],
    action: str | None = None,
    roster: Any = None,
    entity: str | None = None,
    default_actions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = dict(record or {})
    bid = str(block_id or "")
    if bid == "workflow":
        steps = data.get("steps")
        if isinstance(steps, list):
            shaped = []
            first_result = None
            for step in steps:
                if not isinstance(step, dict):
                    shaped.append(step)
                    continue
                item = dict(step)
                child = str(item.get("block") or "").strip()
                inner = item.get("input")
                if not isinstance(inner, dict):
                    inner = {}
                if child:
                    child_action = item.get("action") or default_block_action(
                        child, default_actions
                    )
                    if child_action:
                        item["action"] = child_action
                    params = dict(item.get("params") or {})
                    if child_action:
                        params.setdefault("action", child_action)
                    item["params"] = params
                    inner = prepare_block_input(
                        child, inner, action=child_action, roster=roster,
                        entity=entity, default_actions=default_actions,
                    )
                item["input"] = inner
                if first_result is None and inner:
                    first_result = dict(inner)
                shaped.append(item)
            data["steps"] = shaped
            if not data.get("result") and first_result:
                data["result"] = first_result
        elif not data.get("result"):
            data["result"] = {
                key: value for key, value in data.items()
                if isinstance(value, (str, int, float, bool)) and key != "action"
            } or {"reference": data.get("reference") or "record"}
    if bid == "notification":
        data["channel"] = data.get("channel") if data.get("channel") == "mcp" else "mcp"
        if not data.get("block") and not data.get("tool"):
            peers = [b for b in (roster or []) if b and b != bid]
            data["block"] = peers[0] if peers else "event_bus"
        if not data.get("message"):
            parts = [
                "%s=%s" % (key, value)
                for key, value in data.items()
                if isinstance(value, (str, int, float, bool))
                and key not in ("channel", "block", "tool")
            ]
            data["message"] = "; ".join(parts)[:500] or "platform notification"
    return data
