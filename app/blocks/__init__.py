"""The block registry this platform's own blocks resolve peers from.

The Store's workflow block executes each pipeline step by looking the child
up here, and its notification block drives a named peer the same way. The
platform fills the registry with the peers its capabilities bind that are
served in process, so a prepared pipeline resolves offline.

Each value is a class, not an instance: both callers construct it.
"""

from __future__ import annotations

from typing import Any, Dict

from app.local_blocks import event_bus

BLOCK_REGISTRY: Dict[str, Any] = {
    "event_bus": event_bus.Block,
}


def _mirror_into_vendor() -> None:
    """Register the in-process peers in the vendored blocks' own registry.

    The vendored workflow and notification blocks resolve their children
    from ``vendor.cerebrum.blocks.BLOCK_REGISTRY``. Mirroring the peer here
    is what makes a prepared child resolvable without patching the sealed
    block source.
    """
    try:
        from vendor.cerebrum import blocks as _vendor_blocks

        defs = getattr(_vendor_blocks, "_BLOCK_DEFS", None)
        if isinstance(defs, dict):
            defs.setdefault(
                "event_bus", ("app.local_blocks.event_bus", "Block")
            )
    except Exception:  # noqa: BLE001 - a platform without the vendor tree
        return


_mirror_into_vendor()


def get_block(block_id: str) -> Any:
    return BLOCK_REGISTRY[str(block_id)]


def register(block_id: str, block_class: Any) -> None:
    BLOCK_REGISTRY[str(block_id)] = block_class


__all__ = ["BLOCK_REGISTRY", "get_block", "register"]
