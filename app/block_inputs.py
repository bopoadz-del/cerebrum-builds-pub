"""Constructed block inputs.

A capability feeds the blocks it assigns: it builds the record each block
declares (topic, steps, channels, paths, values) from the domain record.
Callers of the HTTP route never have to know a block's private vocabulary.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

BLOCK_DEFAULT_ACTIONS: Dict[str, str] = {
    "analytics": "track_event",
    "approval_rules": "list",
    "audit": "log",
    "auth": "list_keys",
    "config": "get_all",
    "dashboard": "render",
    "database": "list_tables",
    "email": "validate_address",
    "evidence_chain": "record",
    "formula_executor": "execute",
    "governance_gate": "list_requests",
    "ingestion_provenance": "build",
    "knowledge": "search",
    "memory": "set",
    "notification": "outbox",
    "orchestrator": "run",
    "pdf": "extract",
    "transaction_state_machine": "machine",
    "validation": "validate_pipeline",
    "vector_search": "search",
    "version": "list_versions",
    "version_diff": "diff",
    "workbench": "run",
    "workflow": "run",
}


def default_block_action(block_id: str) -> Optional[str]:
    return BLOCK_DEFAULT_ACTIONS.get(str(block_id))


def prepared_event_bus_step(topic: str, payload: Dict[str, Any], message: str) -> Dict[str, Any]:
    """The prepared event_bus child shape the factory checklist names.

    This platform does not vendor event_bus (it is not in blocks.lock.json),
    so no workflow child is built from it -- a child naming a block the
    product does not ship would fail at run time. The shape is kept here, and
    tested, for the day the block is vendored.
    """
    return {
        "block": "event_bus",
        "action": "publish",
        "input": {
            "topic": str(topic),
            "payload": dict(payload or {}),
            "message": str(message),
            "channel": "mcp",
            "tool": "event_bus",
        },
    }


def audit_input(record: Dict[str, Any], principal: str = "platform") -> Dict[str, Any]:
    reference = str(record.get("reference") or "record")
    return {
        "principal_id": str(record.get("principal_id") or principal),
        "action_name": str(record.get("action_name") or "record"),
        "resource_type": str(record.get("resource_type") or "capability_record"),
        "resource_id": reference,
        "status": str(record.get("status") or "open"),
        "category": str(record.get("category") or "programme"),
        "details": {"reference": reference},
        "tenant_id": str(record.get("tenant_id") or "local"),
    }


def workflow_steps(record: Dict[str, Any], principal: str = "platform") -> Dict[str, Any]:
    """A one-step pipeline whose child is a block this product vendors."""
    reference = str(record.get("reference") or "record")
    return {
        "pipeline_id": "wf-" + reference,
        "steps": [
            {
                "id": "step_0",
                "block": "audit",
                "params": {"action": "log"},
                "input": audit_input(record, principal),
            }
        ],
    }
