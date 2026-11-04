"""Capability handlers.

One module per capability (``app/actions/<capability_id>.py``), each exporting
``CAPABILITY_ID``, ``ENTITY``, ``BLOCK_IDS`` and ``handle(payload) -> dict``.
Nothing is re-exported here on purpose: an eager package import would make
every route import every handler (and every block) at start-up.
"""
