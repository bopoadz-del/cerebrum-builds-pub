"""Construct block inputs from a domain record.

A capability declares WHAT it needs (its model FIELDS); the caller never has to
supply a block's own keys. This module synthesises them: the topic and message
an event carries, the payload dict, the ``mcp`` channel, the ``tool`` name --
and, for workflow children, a fully prepared step with the shape the Store's
workflow block reads.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app import dispatch

MCP_CHANNEL = "mcp"
#: A registered MCP tool the notification block can dispatch to.
EVENT_TOOL = "audit"


def tenant_scope(record: Dict[str, Any]) -> str:
    """The tenant the route resolved, carried on the handler payload."""
    value = str((record or {}).get("_tenant_id") or (record or {}).get("tenant_id") or "").strip()
    return value or "local"


def default_block_action(block_id: str) -> Optional[str]:
    """The action the block's own contract declares (block.json, else code)."""
    return dispatch.default_action(block_id)


def block_action(block_id: str) -> Optional[str]:
    return dispatch.BLOCK_DEFAULT_ACTIONS.get(block_id) or default_block_action(block_id)


def domain_scalars(record: Dict[str, Any]) -> Dict[str, Any]:
    """The record's own scalar fields -- never the raw schema sample alone."""
    out: Dict[str, Any] = {}
    for key, value in (record or {}).items():
        if str(key).startswith("_") or key in ("id", "tenant_id", "created_at", "updated_at"):
            continue
        if isinstance(value, (str, int, float, bool)) and value not in (None, ""):
            out[str(key)] = value
    return out


def event_topic(record: Dict[str, Any], capability_id: str = "") -> str:
    for key in ("event", "event_type", "event_name", "reminder_type", "topic"):
        value = (record or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    reference = str((record or {}).get("reference") or "").strip()
    capability = capability_id or str((record or {}).get("capability_id") or "")
    if reference and capability:
        return f"{capability}.{reference}"
    if reference:
        return reference
    if capability:
        return capability
    return "platform.event"


def event_message(record: Dict[str, Any], capability_id: str = "") -> str:
    reference = str((record or {}).get("reference") or "").strip()
    label = capability_id.replace("_", " ") if capability_id else "record"
    return f"{label} event for {reference}" if reference else f"{label} event"


def prepare_block_input(
    block_id: str,
    record: Dict[str, Any],
    capability_id: str = "",
    **overrides: Any,
) -> Dict[str, Any]:
    """A block-shaped payload, with the block's own dispatch action *not* in it.

    The operation travels as the ``action=`` keyword on ``dispatch.execute``;
    putting it in the payload is the contract the Factory probe refuses.
    """
    scalars = domain_scalars(record)
    tenant = tenant_scope(record)
    payload: Dict[str, Any] = {
        "topic": event_topic(record, capability_id),
        "message": event_message(record, capability_id),
        "channel": MCP_CHANNEL,
        "tool": block_id,
        "payload": scalars,
        "reference": str((record or {}).get("reference") or ""),
        "result": {"reference": str((record or {}).get("reference") or "")},
        "records": [scalars] if scalars else [],
        "items": [scalars] if scalars else [],
        "text": str((record or {}).get("text") or (record or {}).get("message") or ""),
        "tenant_id": tenant,
        "project_id": tenant,
        "principal_id": str((record or {}).get("principal_id") or (record or {}).get("reference") or capability_id or "platform"),
    }
    payload.update({key: value for key, value in overrides.items() if value is not None})
    payload["block"] = block_id
    return payload


def prepare_workflow_input(
    record: Dict[str, Any],
    capability_id: str = "",
    steps: Optional[Iterable[Dict[str, Any]]] = None,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A workflow input whose FIRST child is prepared and whose ``result`` key
    exists -- the Store's workflow and kit shims read ``input['result']``."""
    prepared: List[Dict[str, Any]] = list(steps or [])
    first = prepared[0] if prepared else {}
    first_input = first.get("input") if isinstance(first.get("input"), dict) else {}
    envelope: Dict[str, Any] = {
        "steps": prepared,
        "result": result if isinstance(result, dict) else {
            "block": first.get("block"),
            "action": first.get("action"),
            "topic": first_input.get("topic"),
            "reference": first_input.get("payload", {}).get("reference")
            if isinstance(first_input.get("payload"), dict)
            else None,
        },
        "topic": event_topic(record, capability_id),
        "channel": MCP_CHANNEL,
        "tool": "workflow",
        "payload": domain_scalars(record),
        "reference": str((record or {}).get("reference") or ""),
    }
    return envelope


def attach_result(payload: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach ``result`` to a workflow/shim input without rewriting assignments."""
    if isinstance(payload, dict) and not payload.get("result"):
        payload["result"] = result
    return payload


def failure(result: Dict[str, Any]) -> Optional[str]:
    """The refusal text when a block envelope reports failure, else None."""
    if not isinstance(result, dict):
        return "block returned a non-dict answer"
    if result.get("error_kind") == "unavailable":
        return None
    if result.get("ok") is False or result.get("status") in ("error", "failed", "refused"):
        return str(result.get("error") or result.get("status") or "block refused")
    return None
