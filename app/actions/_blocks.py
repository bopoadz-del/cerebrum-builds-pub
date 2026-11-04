"""One block call, prepared from the record, refused fail-closed.

Every handler reaches its bound blocks through here: the input is constructed
by ``app.block_inputs`` from the domain record, ``action=`` travels as the
keyword the block's own contract declares, and any refusal becomes an error
the caller propagates instead of an ``ok: true`` over a failed block.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.block_inputs import BLOCK_DEFAULT_ACTIONS, prepare_block_input
from app.dispatch import execute, refused


def call(
    block_id: str,
    capability_id: str,
    record: Dict[str, Any],
    tenant_id: str = "",
) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        payload = prepare_block_input(capability_id, block_id, record, tenant_id)
        result = execute(
            block_id,
            payload,
            action=BLOCK_DEFAULT_ACTIONS.get(block_id),
        )
    except Exception as exc:  # noqa: BLE001 - a block failure is a refusal
        return None, "%s failed: %s: %s" % (block_id, type(exc).__name__, exc)
    problem = refused(result)
    if problem:
        return None, "%s refused: %s" % (block_id, problem)
    return result, ""
