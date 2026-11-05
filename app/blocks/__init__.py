"""Block resolver used by the auto-generated vendor adapters.

The adapters for boq_processor, validation and version call
``app.blocks.get_block``. Resolution stays inside the vendored runtime:
locked blocks are still loaded from their pinned vendor path by app.dispatch.
"""

from __future__ import annotations

import importlib

_CLASSES = {
    "boq_processor": ("vendor.cerebrum.blocks.boq_processor", "BOQProcessorBlock"),
    "validation": ("vendor.cerebrum.blocks.validation", "ValidationBlock"),
    "version": ("vendor.cerebrum.blocks.version", "VersionBlock"),
    "event_bus": ("vendor.cerebrum.blocks.event_bus", "EventBusBlock"),
}


def get_block(name: str):
    if name in _CLASSES:
        module_path, class_name = _CLASSES[name]
        return getattr(importlib.import_module(module_path), class_name)
    from vendor.cerebrum.blocks import get_block as _vendored

    return _vendored(name)
