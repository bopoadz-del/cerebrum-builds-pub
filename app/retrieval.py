"""Tenant-scoped retrieval over the corpus the customer supplies.

The platform ships the ingest/query surface and NEVER seeds documents: a RAG
surface is empty until the operator ingests sources. Every chunk carries the
tenant that ingested it, and a query only ever scores that tenant's chunks --
the corpus is reached through the tenant store, never a client-supplied name.

Scoring is lexical (term frequency over inverse document frequency) so a hit is
a real match in stored content, and a query for text nobody ingested comes back
empty instead of echoing the request.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List

from app import store

DOCS = "rag_documents"
CHUNKS = "rag_chunks"
_TOKENS = re.compile(r"[a-z0-9][a-z0-9_-]+")
CHUNK_WORDS = 120
DEFAULT_AUTHORITY = "documents"
AUTHORITY_LABELS = {1: "certified", 2: "documents", 3: "formulas", 4: "procedures"}


def tokenize(text: str) -> List[str]:
    return _TOKENS.findall(str(text or "").lower())


def chunk_text(text: str, size: int = CHUNK_WORDS) -> List[str]:
    words = str(text or "").split()
    if not words:
        return []
    return [" ".join(words[index:index + size]) for index in range(0, len(words), size)]


def ingest(
    text: str,
    tenant_id: str,
    source: str = "",
    title: str = "",
    authority: str = DEFAULT_AUTHORITY,
) -> Dict[str, Any]:
    """Store a document and its chunks for one tenant. Returns the document."""
    body = str(text or "").strip()
    if not body:
        raise ValueError("a document needs text")
    chunks = chunk_text(body)
    document = store.save(
        DOCS,
        {
            "source": source or "operator-upload",
            "title": title or (source or "untitled"),
            "text": body,
            "authority": authority if authority in AUTHORITY_LABELS.values() else DEFAULT_AUTHORITY,
            "chunk_count": len(chunks),
        },
        tenant_id=tenant_id,
    )
    for ordinal, chunk in enumerate(chunks):
        store.save(
            CHUNKS,
            {"document_id": document["id"], "ordinal": ordinal, "text": chunk},
            tenant_id=tenant_id,
        )
    return document


def documents(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    rows = store.list_all(DOCS, tenant_id=tenant_id)
    return rows[:limit]


def _chunks(tenant_id: str) -> List[Dict[str, Any]]:
    return store.list_all(CHUNKS, tenant_id=tenant_id)


def _document_index(tenant_id: str) -> Dict[int, Dict[str, Any]]:
    return {row["id"]: row for row in store.list_all(DOCS, tenant_id=tenant_id)}


def search(query: str, tenant_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Score this tenant's chunks for ``query``; return the matching hits."""
    terms = [term for term in tokenize(query) if len(term) > 1]
    if not terms:
        return []
    chunks = _chunks(tenant_id)
    if not chunks:
        return []
    documents = _document_index(tenant_id)
    total = len(chunks)
    doc_freq: Counter = Counter()
    tokenized: List[tuple] = []
    for chunk in chunks:
        tokens = set(tokenize(chunk.get("text") or ""))
        tokenized.append((chunk, tokens))
        for term in tokens:
            doc_freq[term] += 1

    wanted = set(terms)
    hits: List[Dict[str, Any]] = []
    for chunk, tokens in tokenized:
        matched = wanted & tokens
        if not matched:
            continue
        score = 0.0
        for term in matched:
            frequency = doc_freq.get(term, 0)
            idf = math.log((total + 1) / (frequency + 0.5))
            score += max(idf, 0.05)
        score *= len(matched) / len(wanted)
        if score <= 0.0:
            continue
        document = documents.get(chunk.get("document_id")) or {}
        hits.append(
            {
                "document_id": chunk.get("document_id"),
                "title": document.get("title") or "",
                "source": document.get("source") or "",
                "authority": document.get("authority") or DEFAULT_AUTHORITY,
                "citation": f"doc:{chunk.get('document_id')}#chunk:{chunk.get('ordinal')}",
                "ordinal": chunk.get("ordinal"),
                "text": chunk.get("text") or "",
                "score": round(float(score), 6),
            }
        )
    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[: max(1, int(limit))]


def answer(query: str, tenant_id: str, limit: int = 5) -> Dict[str, Any]:
    """A retrieved answer: hits, citations and the authority label it carries."""
    hits = search(query, tenant_id, limit=limit)
    authority = hits[0]["authority"] if hits else "none"
    return {
        "ok": True,
        "query": query,
        "hits": hits,
        "citations": [hit["citation"] for hit in hits],
        "authority": authority,
        "authority_label": f"layer {2} {AUTHORITY_LABELS[2]}" if hits else "no source retrieved",
        "grounded": bool(hits),
    }


def summarise_hits(hits: Iterable[Dict[str, Any]]) -> str:
    return " ".join(str(hit.get("text") or "") for hit in hits)[:1200]
