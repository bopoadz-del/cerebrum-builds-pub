"""The keyword action each bound block declares.

Handlers pass these through ``execute(..., action=...)`` -- never inside
the payload record. The map is populated from the blocks' own contracts
(block.json action/operation defaults and the defaults their code reads)
in app.dispatch.
"""

from __future__ import annotations

from typing import Optional

from app.dispatch import BLOCK_DEFAULT_ACTIONS


def default_block_action(block_id: str) -> Optional[str]:
    return BLOCK_DEFAULT_ACTIONS.get(str(block_id))


def construct_inputs(block_id: str, record: Optional[dict] = None) -> dict:
    """A flat input record for a block, built from the domain record."""
    return dict(record or {})
