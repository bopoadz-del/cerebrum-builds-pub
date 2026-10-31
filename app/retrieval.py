"""Tenant-scoped document retrieval over the ingested corpus.

Documents arrive through the RAG ingest route (upload) or the M365 ingestion
capability. Retrieval is lexical with inverse-document-frequency weighting
over sentence-sized chunks, so an answer can be grounded in the passages
that actually matched the question. No corpus is fabricated: an empty store
answers honestly that there is nothing to cite.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List

from app import store
from app.tenancy import current_tenant

ENTITY = "rag_document"
_WORD = re.compile(r"[a-z0-9][a-z0-9_-]*")
_SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "be", "by", "with", "at", "from", "that", "this", "it",
    "as", "we", "our", "what", "which", "who", "when", "where", "how", "do",
}


def _tokens(text: str) -> List[str]:
    return [t for t in _WORD.findall(str(text or "").lower()) if t not in _STOP and len(t) > 1]


def _chunks(text: str, limit: int = 420) -> List[str]:
    pieces: List[str] = []
    for paragraph in str(text or "").split("\n\n"):
        for sentence in _SENTENCE.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            while len(sentence) > limit:
                pieces.append(sentence[:limit])
                sentence = sentence[limit:]
            if sentence:
                pieces.append(sentence)
    return pieces or ([str(text).strip()] if str(text or "").strip() else [])


def ingest(text: str, source: str = "upload", document_name: str = "",
           document_type: str = "bom", tenant_id: str = "") -> Dict[str, Any]:
    tenant = tenant_id or current_tenant()
    body = str(text or "")
    if not body.strip():
        raise ValueError("document text is required")
    saved = store.save(
        ENTITY,
        {
            "reference": document_name or (source or "upload"),
            "status": "open",
            "text": body,
            "source": source or "upload",
            "document_name": document_name or "",
            "document_type": document_type or "bom",
        },
        tenant_id=tenant,
    )
    return saved


def _documents(tenant_id: str) -> List[Dict[str, Any]]:
    return store.list_all(ENTITY, tenant_id=tenant_id)


def search(query: str, top_k: int = 5, tenant_id: str = "") -> List[Dict[str, Any]]:
    tenant = tenant_id or current_tenant()
    question = _tokens(query)
    if not question:
        return []
    documents = _documents(tenant)
    if not documents:
        return []
    chunk_rows: List[Dict[str, Any]] = []
    for document in documents:
        for index, chunk in enumerate(_chunks(document.get("text", ""))):
            chunk_rows.append(
                {
                    "document_id": document.get("id"),
                    "document_name": document.get("document_name") or document.get("reference") or "",
                    "source": document.get("source") or "upload",
                    "chunk_index": index,
                    "text": chunk,
                    "tokens": _tokens(chunk),
                }
            )
    if not chunk_rows:
        return []
    doc_freq = Counter()
    for row in chunk_rows:
        for token in set(row["tokens"]):
            doc_freq[token] += 1
    total = len(chunk_rows)
    scored: List[Dict[str, Any]] = []
    for row in chunk_rows:
        counts = Counter(row["tokens"])
        score = 0.0
        for term in question:
            if not counts.get(term):
                continue
            weight = math.log((1.0 + total) / (1.0 + doc_freq.get(term, 0))) + 1.0
            score += counts[term] * weight
        if score > 0:
            scored.append({**row, "score": round(score, 4)})
    scored.sort(key=lambda item: (item["score"], -item["chunk_index"]), reverse=True)
    results = []
    for row in scored[: max(1, int(top_k))]:
        results.append(
            {
                "document_id": row["document_id"],
                "document_name": row["document_name"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "score": row["score"],
                "text": row["text"],
            }
        )
    return results


def corpus_size(tenant_id: str = "") -> int:
    return len(_documents(tenant_id or current_tenant()))


def citations(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for index, row in enumerate(results, start=1):
        out.append(
            {
                "label": f"[Source {index}]",
                "document_id": row.get("document_id"),
                "document_name": row.get("document_name"),
                "source": row.get("source"),
                "chunk_index": row.get("chunk_index"),
                "score": row.get("score"),
                "text": row.get("text"),
            }
        )
    return out
