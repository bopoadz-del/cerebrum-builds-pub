"""Cerebrum Executive Programs -- product package.

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
PRODUCT_NAME = "Cerebrum Executive Programs"


def _bind_domain_ops() -> None:
    """Declare the capabilities ``app.domain_ops`` performs through the kernel.

    ``domain_ops`` is the kernel's S12 path (create/read/update/delete/list/
    enqueue/process/refuse through ``execute_action``). It ships with an empty
    registry so it carries no product knowledge; the product binds its own
    capabilities here, once, from ``app.models``.
    """
    try:
        from app import kernel_bridge
    except Exception:  # pragma: no cover - a broken tree fails at the gate
        return
    kernel_bridge.bind_domain_ops()


_bind_domain_ops()
