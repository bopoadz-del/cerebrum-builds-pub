"""Offline compatibility surface for a locked block's own dependency.

The Store's ``knowledge`` block imports ``vendor.cerebrum.core.vector_store``
at module load and calls it only when a ``project_id`` is supplied. That
module is not part of the sealed vendor snapshot this product carries, so the
import fails before the block can dispatch. The platform already owns a real,
tenant-scoped lexical index (``app.retrieval``); this module publishes it under
the name the block imports, so retrieval still answers from stored content and
never from a stub.

Nothing here is a fallback for a missing capability: a query with no ingested
chunks returns an empty list, which the block reports honestly.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List

from app import retrieval

MODULE_NAME = "vendor.cerebrum.core.vector_store"


async def search_vectors(
    project_id: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.3,
    **_kwargs: Any,
) -> List[Dict[str, Any]]:
    """Score this tenant's stored chunks for ``query``.

    ``project_id`` is the tenant the corpus is scoped to: the block already
    refuses retrieval without one, and the index it reaches is the product's
    tenant-scoped store, never a client-supplied corpus name.
    """
    tenant = str(project_id or "").strip()
    if not tenant:
        return []
    hits = retrieval.search(str(query or ""), tenant, limit=max(1, int(top_k)))
    results: List[Dict[str, Any]] = []
    for hit in hits:
        score = float(hit.get("score") or 0.0)
        if score < float(threshold):
            continue
        results.append(
            {
                "id": hit.get("citation"),
                "text": hit.get("text") or "",
                "score": score,
                "source": hit.get("source") or hit.get("title") or "operator-upload",
                "title": hit.get("title") or "",
                "authority": hit.get("authority") or retrieval.DEFAULT_AUTHORITY,
                "project_id": tenant,
            }
        )
    return results


class _VectorStoreModule(types.ModuleType):
    """A module object that also satisfies ``from ... import vector_store``."""

    search_vectors = staticmethod(search_vectors)


def install() -> None:
    """Publish the shim only when the vendor module genuinely is absent."""
    package_name = "vendor.cerebrum.core"
    try:
        __import__(MODULE_NAME)
        return
    except Exception:  # noqa: BLE001 - absent, or broken by a missing sibling
        pass
    package = sys.modules.get(package_name)
    if package is None:
        try:
            package = __import__(package_name, fromlist=["*"])
        except Exception:  # noqa: BLE001 - no vendor tree in a dev checkout
            return
    module = _VectorStoreModule(MODULE_NAME)
    module.__file__ = __file__
    sys.modules[MODULE_NAME] = module
    setattr(package, "vector_store", module)
