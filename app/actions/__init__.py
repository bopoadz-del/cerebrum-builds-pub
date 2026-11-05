"""Capability handlers live in one module per capability; nothing is
re-exported here on purpose (an eager import of every handler would make the
route table and the handlers import each other)."""

from __future__ import annotations
