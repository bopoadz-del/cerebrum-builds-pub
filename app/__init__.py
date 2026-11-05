"""Harbourline Civil Works contracts-administration platform."""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"

# The product's capability declaration feeds the kernel's S12 domain specs at
# import time, so every path (HTTP, queue, kernel) reads one roster.
from app import domain_registry as _domain_registry  # noqa: E402,F401
