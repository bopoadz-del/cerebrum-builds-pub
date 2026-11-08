"""Block input construction shared by the capability handlers.

The caller never supplies block-specific keys (topic, sql, file paths,
team_id, channel, steps); the handler synthesises them from the domain
record. ``default_block_action`` is the block's own declared action.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.dispatch import BLOCK_DEFAULT_ACTIONS


def default_block_action(block_id: str) -> Optional[str]:
    return BLOCK_DEFAULT_ACTIONS.get(block_id)


def storage_root() -> Path:
    """Where block input artefacts are staged.

    The record store still declares its one root through STORAGE_PATH and
    fails closed without it (app.db). This helper only writes the input
    files a block reads (a BOQ CSV, a register text); a direct ``handle()``
    call with no deployment root therefore stages them under a per-process
    scratch directory instead of refusing to do the computation at all.
    """
    raw = (os.getenv("STORAGE_PATH") or "").strip()
    root = Path(raw) if raw else Path(tempfile.gettempdir()) / ("harbourline-scratch-%d" % os.getpid())
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_text_file(name: str, content: str) -> str:
    path = storage_root() / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def ensure_boq_csv(items: List[Dict[str, Any]]) -> str:
    """Write the BOQ basis as a CSV the boq_processor block can parse."""
    lines = ["Item,Description,Unit,Qty,Rate"]
    for item in items:
        description = str(item.get("description") or "").replace(",", " ")
        lines.append(
            "%s,%s,%s,%s,%s"
            % (
                item.get("item") or item.get("item_key") or "",
                description,
                item.get("unit") or "",
                item.get("qty") if item.get("qty") is not None else item.get("quantity") or 0,
                item.get("rate") if item.get("rate") is not None else item.get("unit_cost") or 0,
            )
        )
    return ensure_text_file("boq_basis.csv", "\n".join(lines) + "\n")

