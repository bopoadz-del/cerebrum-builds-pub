"""Offline grounded answering over the platform's own corpus.

This platform has no network and no hosted model. ``answer`` is a deterministic
extractive reader: it ranks persisted chunks with ``app.retrieval`` and returns
the highest-scoring passage verbatim, with its document citation. It never
invents an answer -- when nothing matches it says so and returns no hits.

The capability handlers use their bound Store blocks for domain reasoning; this
module exists for the operator console and the RAG query surface, where a
grounded excerpt is the useful answer.
"""

from __future__ import annotations

from typing import Any, Dict

from app import retrieval

MODEL = "offline-extractive-reader.v1"


def answer(question: str, tenant_id: str, limit: int = 5) -> Dict[str, Any]:
    found = retrieval.search(question, tenant_id, limit=limit)
    hits = found.get("hits") or []
    cited = retrieval.citations(hits, tenant_id)
    if not hits:
        return {
            "ok": True,
            "model": MODEL,
            "query": question,
            "answer": "",
            "hits": [],
            "citations": [],
            "grounded": False,
            "note": "no passage in this tenant's corpus matches the question",
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
    }
