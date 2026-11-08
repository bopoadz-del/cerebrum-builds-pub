"""Offline answer policy.

This platform runs with no network. An "answer" is therefore extractive: it
quotes the ingested chunks the caller's tenant owns and names the authority
layer. It will not generate a sentence the source does not support; with no
retrieval hit it says so and refuses to invent one.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import retrieval


class NoGroundedAnswer(RuntimeError):
    """Raised when no ingested text supports an answer."""


def answer(tenant_id: str, question: str, limit: int = 3) -> Dict[str, Any]:
    hits: List[Dict[str, Any]] = retrieval.search(tenant_id, question, limit=limit)
    if not hits:
        raise NoGroundedAnswer(
            "no ingested document supports an answer; ingest a source first"
        )
    quotes = [str(hit.get("chunk") or "")[:1200] for hit in hits]
    return {
        "question": question,
        "answer": "\n\n".join(quotes),
        "grounded": True,
        "citations": [
            {"document_id": hit.get("document_id"), "chunk_id": hit.get("id")}
            for hit in hits
        ],
        "authority": dict(retrieval.AUTHORITY),
    }
