"""Answered questions over the tenant's own documents.

The platform runs offline: no hosted model is called.  An answer is composed
from the retrieved chunks only -- every sentence it states is quoted from a
chunk with its citation -- and a question the corpus does not cover is
refused instead of answered from model memory.  That refusal is the point:
the uploaded contract and BOQ are the source of record.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.authority import label

MAX_QUOTE = 400


def answer(query: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    question = str(query or "").strip()
    if not chunks:
        return {
            "answer": "",
            "claims": [],
            "citations": [],
            "refused": True,
            "reason": "no document in this tenant's corpus covers the question",
            "authority": label("documents"),
        }
    claims: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        quote = text[:MAX_QUOTE]
        citation = {
            "index": index,
            "source": chunk.get("source"),
            "chunk_id": chunk.get("id"),
            "score": chunk.get("score"),
            "quote": quote,
        }
        citations.append(citation)
        claims.append({"text": quote, "evidence": [chunk.get("id")]})
    body = " ".join(citation["quote"] for citation in citations)
    return {
        "answer": body,
        "claims": claims,
        "citations": citations,
        "refused": not bool(claims),
        "reason": "" if claims else "retrieved chunks carried no text",
        "authority": label("documents"),
        "query": question,
    }
