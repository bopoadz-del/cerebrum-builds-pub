"""HTTP routes over the capability actions.

The routes live in app.routes so the Factory's ROUTE_ENTITIES contract and
the test suite read one module; this package re-exports that router.
"""

from app.routes import router

__all__ = ["router"]
