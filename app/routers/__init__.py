"""HTTP routes over the capability actions.

The route objects live in :mod:`app.routes`; this package is the stable import
surface named by the platform OUTPUT contract and re-exports them unchanged.
"""

from app.routes import KERNEL, ROUTE_AUTHORITY, ROUTE_ENTITIES, ROUTER

__all__ = ["KERNEL", "ROUTER", "ROUTE_ENTITIES", "ROUTE_AUTHORITY"]
