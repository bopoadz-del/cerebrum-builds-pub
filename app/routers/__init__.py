"""HTTP routers over the capability handlers.

The route bodies live in ``app.routes`` (capabilities and kernel surfaces) and
``app.rag_routes`` (retrieval); this package is the import-friendly surface a
deployment or a UI build can mount without reaching into module internals.
There is one API: these are aliases, not a second implementation.
"""

from __future__ import annotations

from app.rag_routes import ROUTER as RAG_ROUTER
from app.routes import KERNEL, ROUTER

__all__ = ["KERNEL", "ROUTER", "RAG_ROUTER"]
