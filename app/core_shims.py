"""Compatibility shims for the vendored runtime slice.

The locked ``knowledge`` block imports ``vendor.cerebrum.core.vector_store``,
which the runtime slice does not carry.  Rather than re-implement the block,
this module supplies the missing adapter backed by the platform's own
retrieval surface -- so the block answers from real, tenant-scoped chunks that
the customer ingested, and never from a fabricated corpus.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List


def _build_vector_store() -> types.ModuleType:
    module = types.ModuleType("vendor.cerebrum.core.vector_store")
    module.__doc__ = "Adapter over app.retrieval for the vendored knowledge block."

    async def search_vectors(
        project_id: str,
        query: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> List[Dict[str, Any]]:
        from app import retrieval

        tenant = str(project_id or "").strip()
        if not tenant:
            return []
        try:
            hits = retrieval.search(query, tenant, top_k=max(1, int(top_k)))
        except Exception:
            return []
        return [
            {
                "id": hit.get("id"),
                "text": hit.get("text"),
                "score": hit.get("score", 0.0),
                "metadata": {"source": hit.get("source"), "tenant_id": tenant},
            }
            for hit in hits
            if float(hit.get("score") or 0.0) >= float(threshold)
        ]

    async def add_vectors(*args, **kwargs):
        raise NotImplementedError("ingestion goes through POST /v1/rag/ingest")

    module.search_vectors = search_vectors
    module.add_vectors = add_vectors
    return module


def install() -> None:
    if "vendor.cerebrum.core.vector_store" in sys.modules:
        return
    shim = _build_vector_store()
    sys.modules["vendor.cerebrum.core.vector_store"] = shim
    try:
        import vendor.cerebrum.core as core

        setattr(core, "vector_store", shim)
    except Exception:
        pass
