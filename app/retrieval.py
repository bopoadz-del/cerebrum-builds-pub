"""Lexical retrieval over the tenant's persisted document chunks.

The platform's corpus is the uploaded contract/BOQ and the records derived from
them. Retrieval is deterministic token-overlap ranking over SQLite rows: no
network, no external vector service, and every hit names the document it came
from. ``app/rag_routes.py`` exposes it over HTTP; ``app/llm.py`` grounds its
answers in it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app import store

MAX_HITS = 5
_STOPWORDS = frozenset(
    "the a an of and or to in for on at by is are was were be been with from as it its this that these those".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> List[str]:
    return [token for token in _TOKEN.findall(str(text or "").lower()) if token not in _STOPWORDS]


def chunk_text(text: str, size: int = 120) -> List[str]:
    words = str(text or "").split()
    if not words:
        return []
    return [" ".join(words[index : index + size]) for index in range(0, len(words), size)]


def search(question: str, tenant_id: str, limit: int = MAX_HITS) -> Dict[str, Any]:
    terms = set(tokens(question))
    if not terms:
        return {"query": question, "hits": [], "total": 0}
    scored: List[Dict[str, Any]] = []
    for chunk in store.list_all("rag_chunks", tenant_id=tenant_id):
        text = str(chunk.get("text") or "")
        words = set(tokens(text))
        overlap = terms & words
        if not overlap:
            continue
        scored.append(
            {
                "text": text,
                "score": round(len(overlap) / float(len(terms)), 4),
                "matched": sorted(overlap),
                "document_id": chunk.get("document_id"),
                "ordinal": chunk.get("ordinal"),
            }
        )
    scored.sort(key=lambda row: (-row["score"], row.get("document_id") or 0, row.get("ordinal") or 0))
    hits = scored[: max(1, int(limit))]
    return {"query": question, "hits": hits, "total": len(hits)}


def citations(hits: List[Dict[str, Any]], tenant_id: str) -> List[Dict[str, Any]]:
    documents: Dict[Any, Dict[str, Any]] = {}
    for document in store.list_all("rag_documents", tenant_id=tenant_id):
        documents[document.get("id")] = document
    out = []
    for hit in hits:
        document = documents.get(hit.get("document_id")) or {}
        out.append(
            {
                "document_id": hit.get("document_id"),
                "source": document.get("source"),
                "title": document.get("title"),
                "ordinal": hit.get("ordinal"),
                "score": hit.get("score"),
            }
        )
    return out
