"""Offline grounded answering over the platform's own source-of-record.

There is no hosted model and no network in this product. ``answer`` is a
deterministic extractive reader: it ranks the tenant's persisted source and
register records through ``app.retrieval`` and returns the best passage with
its citation and authority label. It never invents an answer; when nothing
matches it says so and returns no hits.
"""

from __future__ import annotations

from typing import Any, Dict

from app import retrieval

MODEL = "offline-extractive-reader.v1"
AUTHORITY = "layer 2 documents"


def answer(question: str, tenant_id: str, limit: int = 5) -> Dict[str, Any]:
    found = retrieval.search(question, tenant_id, limit=limit)
    hits = found.get("hits") or []
    cited = retrieval.citations(hits)
    if not hits:
        return {
            "ok": True,
            "model": MODEL,
            "query": question,
            "answer": "",
            "hits": [],
            "citations": [],
            "grounded": False,
            "authority": AUTHORITY,
            "note": "no source-of-record passage matches the question for this tenant",
        }
    return {
        "ok": True,
        "model": MODEL,
        "query": question,
        "answer": hits[0]["text"],
        "hits": hits,
        "citations": cited,
        "grounded": True,
        "confidence": hits[0].get("score", 0.0),
        "authority": AUTHORITY,
    }
