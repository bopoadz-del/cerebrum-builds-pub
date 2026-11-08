"""Deterministic, offline answer synthesis over retrieved evidence.

No network and no provider key: the answer is extracted from the retrieved
chunks and every sentence carries the citation of the chunk it came from.
An answer with no evidence is empty -- this module never invents a claim.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def synthesize(question: str, chunks: List[Dict[str, Any]], limit: int = 3) -> Dict[str, Any]:
    if not chunks:
        return {
            "answer": "",
            "citations": [],
            "grounded": False,
            "reason": "no retrieved evidence",
        }
    sentences: List[str] = []
    citations: List[Dict[str, Any]] = []
    for index, chunk in enumerate(chunks[:limit], start=1):
        text = str(chunk.get("text") or "").strip()
        if not text:
            continue
        pieces = [part.strip() for part in re.split(r"(?<=[.;])\s+", text) if part.strip()]
        excerpt = " ".join(pieces[:2])[:400]
        sentences.append("%s [Source %d]" % (excerpt, index))
        citations.append({
            "source": chunk.get("source"),
            "source_number": index,
            "score": chunk.get("score"),
        })
    return {
        "answer": " ".join(sentences),
        "citations": citations,
        "grounded": bool(sentences),
        "reason": "" if sentences else "no usable chunk text",
    }
