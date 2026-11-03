"""HTTP route package.

The platform serves one API. The capability surface (auth -> declared
connector refusal -> validation -> handler -> tenant-scoped persistence)
lives in app/routes.py; this package is the import seam the app factory
uses, so a caller has one name for the router whether it is assembled
here or there.
"""

from __future__ import annotations

from app.routes import ROUTE_ENTITIES, router

__all__ = ["router", "ROUTE_ENTITIES"]
