"""Tenant-scoped document retrieval: the ingest/query surface.

A retrieval corpus is empty until the customer supplies sources. This module
stores what they send and finds it again by term overlap -- no seeded
documents, no fabricated corpus. Every call is scoped by the tenant the
authenticated principal resolved to; a caller cannot name another tenant's
corpus.

Scoring is deliberately simple and inspectable: an IDF-weighted term overlap
over the tenant's own rows, so a query for a phrase that was never ingested
returns nothing rather than an echo of the request.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import store

ENTITY = "rag_documents"

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]+")
_STOP = frozenset(
    "the a an and or of to in on for with by as at from is are was were be been "
    "this that these those it its into their our your we you they he she not no "
    "do does did done can could may might will would shall should about".split()
)


def _tokens(text: str) -> List[str]:
    return [token.lower() for token in _TOKEN.findall(str(text or "")) if token.lower() not in _STOP]


def ingest(
    tenant_id: str,
    text: str,
    source: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Store one document for the caller's tenant and return the stored row."""
    body = str(text or "").strip()
    if not body:
        raise ValueError("a document needs text to ingest")
    reference = str(source or "").strip() or "source-%s" % datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    record = {
        "reference": reference,
        "status": "open",
        "text": body,
        "content": body,
        "source": reference,
        "characters": len(body),
        "terms": len(_tokens(body)),
        "metadata": dict(metadata or {}),
    }
    return store.save(ENTITY, record, tenant_id)


def documents(tenant_id: str) -> List[Dict[str, Any]]:
    return store.list_all(ENTITY, tenant_id)


def search(tenant_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Rank the tenant's documents against the query, best first."""
    terms = _tokens(query)
    rows = documents(tenant_id)
    if not terms or not rows:
        return []
    corpus = [Counter(_tokens(row.get("text") or row.get("content") or "")) for row in rows]
    total = len(rows)
    document_frequency = Counter()
    for counts in corpus:
        for term in set(counts):
            document_frequency[term] += 1
    query_counts = Counter(terms)
    scored: List[Dict[str, Any]] = []
    for row, counts in zip(rows, corpus):
        score = 0.0
        matched = []
        for term, query_weight in query_counts.items():
            if not counts.get(term):
                continue
            idf = math.log((total + 1.0) / (document_frequency.get(term, 0) + 0.5))
            score += (1.0 + math.log(counts[term])) * idf * query_weight
            matched.append(term)
        if score > 0:
            scored.append(
                {
                    "id": row.get("id"),
                    "source": row.get("source") or row.get("reference"),
                    "reference": row.get("reference"),
                    "content": row.get("text") or row.get("content") or "",
                    "score": round(score, 6),
                    "matched_terms": sorted(set(matched)),
                }
            )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, int(limit or 5))]


def answer(tenant_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    """A retrieval answer that carries its authority label."""
    hits = search(tenant_id, query, limit=limit)
    return {
        "ok": True,
        "query": query,
        "results": hits,
        "total": len(hits),
        "corpus_size": len(documents(tenant_id)),
        "authority": {"layer": 2, "label": "documents", "source": "tenant_corpus"},
    }
