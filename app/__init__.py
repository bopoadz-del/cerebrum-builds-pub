"""Harbourline Civil Works contracts administration -- product package.

The package import is deliberately cheap: importing ``app`` must work with an
EMPTY environment (CI boots ``import app.main`` before any credential exists),
so nothing here reads a setting, opens a database, or loads a block. The only
work done here is binding the kernel's domain-operation registry to this
product's capabilities, which is pure declaration built from ``app.models``.
"""

from __future__ import annotations

__all__ = ["PRODUCT_ID", "PRODUCT_NAME", "__version__"]

__version__ = "1.0.0"
PRODUCT_ID = "product"
PRODUCT_NAME = "Harbourline Civil Works contracts administration"


def _bind_domain_ops() -> None:
    try:
        from app import kernel_bridge
    except Exception:  # pragma: no cover - a broken tree fails at the gate
        return
    kernel_bridge.bind_domain_ops()


_bind_domain_ops()
