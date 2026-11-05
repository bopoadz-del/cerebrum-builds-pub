"""Tenant-scoped lexical retrieval over records the customer supplies.

There is no seeded corpus: an empty register retrieves nothing until the
operator creates documents. Ranking is deterministic token overlap, so a hit
is explainable and never a model's invention.
"""

from __future__ import annotations

import re
from typing import Iterable, List

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(str(text or "").lower())


def score(query: str, text: str) -> float:
    q = set(tokenize(query))
    if not q:
        return 0.0
    t = set(tokenize(text))
    return len(q & t) / float(len(q))


def retrieve(query: str, documents: Iterable[dict], limit: int = 10) -> List[dict]:
    ranked = []
    for document in documents or []:
        blob = " ".join(str(document.get(key) or "") for key in ("title", "reference", "description", "source_document"))
        value = score(query, blob)
        if value > 0:
            ranked.append((value, document))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("id"))))
    return [{"score": round(value, 4), "record": document} for value, document in ranked[:limit]]
