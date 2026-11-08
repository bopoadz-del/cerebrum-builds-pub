"""Capability handlers.

Each module exports ``CAPABILITY_ID``, ``ENTITY``, ``BLOCK_IDS`` and
``handle(payload) -> dict``. Nothing is re-exported here: eager imports would
make the package import every handler (and every bound block) at once.
"""
