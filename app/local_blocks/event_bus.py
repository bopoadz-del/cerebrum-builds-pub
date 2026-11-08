"""Offline in-process event bus: publish an event to a topic.

The Store's event bus notifies a peer over MCP or a webhook. This offline
peer accepts the same published shape (topic, payload, message, channel,
tool) and keeps an in-process log -- it never dials out. It is what makes a
prepared workflow child resolvable when the platform runs without the
vendored event bus.

Scope READS: caller input (topic, payload, message, channel).
Scope WRITES: an in-process event log only -- no file, no network.
Scope NEVER: no outbound connection of any kind.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.local_blocks._common import Shim, error, ok, run_block

BLOCK_ID = "event_bus"

_EVENTS: List[Dict[str, Any]] = []


def published() -> List[Dict[str, Any]]:
    return [dict(event) for event in _EVENTS]


def reset() -> None:
    _EVENTS.clear()


def ensure_registered() -> None:
    """Expose this peer to the vendored blocks' lazy registry.

    The vendored workflow and notification blocks resolve a child through
    ``vendor.cerebrum.blocks.BLOCK_REGISTRY``; adding the def here (in
    memory) makes a prepared child resolvable without patching the sealed
    block source.
    """
    try:
        from vendor.cerebrum import blocks as _vendor_blocks

        defs = getattr(_vendor_blocks, "_BLOCK_DEFS", None)
        if isinstance(defs, dict):
            defs.setdefault("event_bus", ("app.local_blocks.event_bus", "Block"))
    except Exception:  # noqa: BLE001 - a platform without the vendor tree
        return


class Block(Shim):
    BLOCK_ID = BLOCK_ID
    DEFAULT_ACTION = "publish"

    def handle(self, input_data: Any, action: Optional[str] = None,
               params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = dict(input_data) if isinstance(input_data, dict) else {}
        call = str(action or data.get("action") or self.DEFAULT_ACTION)
        if call == "publish":
            topic = str(data.get("topic") or "").strip()
            if not topic:
                return error(BLOCK_ID, call, "topic required")
            payload = data.get("payload")
            if not isinstance(payload, dict):
                payload = {
                    key: value for key, value in data.items()
                    if key not in ("topic", "message", "channel", "tool", "block", "action")
                    and isinstance(value, (str, int, float, bool))
                }
            channel = str(data.get("channel") or "").strip().lower() or "mcp"
            if channel not in ("mcp", "email", "slack", "webhook", "inprocess"):
                return error(BLOCK_ID, call, "unknown channel: %s" % channel)
            message = str(data.get("message") or "").strip()
            if not message:
                return error(BLOCK_ID, call, "message required")
            _EVENTS.append({
                "topic": topic,
                "payload": dict(payload),
                "message": message,
                "channel": channel,
                "tool": str(data.get("tool") or BLOCK_ID),
            })
            return ok(BLOCK_ID, call, {
                "topic": topic,
                "published": True,
                "delivered": len(_EVENTS),
                "payload": dict(payload),
            })
        if call == "get_topology":
            topics = sorted({event["topic"] for event in _EVENTS})
            return ok(BLOCK_ID, call, {"topics": topics, "events": len(_EVENTS)})
        return error(BLOCK_ID, call, "Unknown action: %s" % call)


def run(**kwargs: Any) -> Dict[str, Any]:
    return run_block(BLOCK_ID, Block, kwargs)
