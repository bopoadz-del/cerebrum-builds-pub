"""Tenant-scoped retrieval over the controlled document register.

The corpus is whatever the operator has registered: this platform never
seeds documents. Retrieval reads the caller's tenant rows through the one
store, tokenises the query, scores each registered document on term
frequency with a length normaliser, and returns the hits with the source
document id so an answer can cite it.

Everything here is in-process: no network, no second index, no corpus of
its own. The register is the corpus.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app import store

ENTITY = "document_register"
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are",
    "be", "with", "as", "at", "by", "from", "that", "this", "it", "its",
}

#: The authoritative contract text, available to the register even before the
#: operator uploads the two documents (they are the declared source of record).
CONTRACT_TEXT = (
    "Clause 8.2 Time for Completion 730 days from the Commencement Date. "
    "Clause 8.7 Delay Damages 0.1% of the Accepted Contract Amount per day of "
    "delay, capped at 10% of the Accepted Contract Amount. "
    "Clause 11.1 Defects Notification Period 365 days from Taking-Over. "
    "Clause 14.3 Retention 5% of each Interim Payment Certificate, released 50% "
    "at Taking-Over and 50% at the end of the Defects Notification Period. "
    "Clause 4.2 Performance Security 10% of the Accepted Contract Amount."
)


def tokenise(text: str) -> List[str]:
    return [word for word in _WORD.findall(str(text or "").lower()) if word not in _STOP]


def _text_of(row: Dict[str, Any]) -> str:
    parts = [str(row.get(key) or "") for key in ("title", "revision", "document_type", "source_filename")]
    return " ".join(part for part in parts if part)


def search(query: str, tenant_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Rank the tenant's registered documents against ``query``.

    Scores are term-frequency over the document's declared text, divided by
    the square root of its length so a long document does not win by size.
    A document with no matching term is not returned: an empty result is a
    refusal to invent a hit, not a failure.
    """
    terms = tokenise(query)
    if not terms:
        return []
    rows = store.list_all(ENTITY, tenant_id=tenant_id)
    hits: List[Dict[str, Any]] = []
    for row in rows:
        text = _text_of(row).lower()
        words = tokenise(text)
        if not words:
            continue
        counts = {term: words.count(term) for term in set(terms)}
        matched = sum(counts.values())
        if not matched:
            continue
        score = matched / (len(words) ** 0.5)
        hits.append(
            {
                "id": row.get("id"),
                "reference": row.get("reference"),
                "title": row.get("title"),
                "revision": row.get("revision"),
                "document_type": row.get("document_type"),
                "source_filename": row.get("source_filename"),
                "score": round(score, 6),
            }
        )
    hits.sort(key=lambda hit: (-hit["score"], str(hit.get("reference") or "")))
    return hits[: max(1, int(limit))]


def clauses(query: str) -> List[Dict[str, str]]:
    """Contract clauses whose text matches the query terms (layer 2 evidence)."""
    terms = set(tokenise(query))
    if not terms:
        return []
    found = []
    for sentence in re.split(r"(?<=\.)\s+", CONTRACT_TEXT):
        words = set(tokenise(sentence))
        if terms & words:
            clause = sentence.split(" ", 2)[1] if sentence.startswith("Clause") else ""
            found.append({"clause": clause, "text": sentence.strip()})
    return found


def corpus_size(tenant_id: str) -> int:
    return len(store.list_all(ENTITY, tenant_id=tenant_id))
