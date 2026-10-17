"""Factory-grounded persist envelope shared by capability handlers."""

from __future__ import annotations

from typing import Any, Dict, List

from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
from app.schema import get_spec
from app.store import save as store_save


def persist_record(capability_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    spec = get_spec(capability_id)
    return store_save(spec["entity"], payload)


def run_blocks(
    capability_id: str,
    block_ids: List[str],
    prepared: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute every declared block id with a constructed input and keyword action."""
    results: Dict[str, Any] = {}
    for block_id in block_ids:
        block_input = prepared.get(block_id, {})
        action = BLOCK_DEFAULT_ACTIONS.get(block_id)
        results[block_id] = execute(block_id, block_input, action=action)
    return results


def ok_envelope(
    capability_id: str,
    payload: Dict[str, Any],
    block_results: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    saved = persist_record(capability_id, payload)
    return {
        "ok": True,
        "capability": capability_id,
        "entity": get_spec(capability_id)["entity"],
        "record": saved,
        "blocks": block_results or {},
    }
