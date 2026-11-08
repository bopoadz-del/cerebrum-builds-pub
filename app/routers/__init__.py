"""HTTP routers over the capability actions.

``app.routes`` carries the platform surface; this package is its import
point so a deployment can mount the same router from either name.
"""

from app.routes import router

__all__ = ["router"]
