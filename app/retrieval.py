"""Retrieval over the uploaded source documents.

The corpus is exactly the two documents the customer supplied -- the contract
excerpt and the priced BOQ. Nothing is seeded or invented: every passage
carries the document id and clause/item it came from, so a retrieved answer
can cite its source.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Iterable, List

from app import contract

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "by", "is",
    "are", "be", "at", "with", "from", "as", "that", "this", "it",
}


def _tokens(text: str) -> List[str]:
    return [word for word in _WORD.findall(str(text).lower()) if word not in _STOP]


def passages() -> List[Dict[str, Any]]:
    """Every retrievable passage, with its source label."""
    rows: List[Dict[str, Any]] = []
    for clause in contract.clauses():
        rows.append(
            {
                "id": f"clause-{clause.get('ref')}-{clause.get('heading', '').replace(' ', '-')}",
                "source": contract.contract_document_id(),
                "kind": "clause",
                "ref": str(clause.get("ref")),
                "label": f"Clause {clause.get('ref')} {clause.get('heading', '')}".strip(),
                "text": str(clause.get("text") or ""),
                "authority_layer": "documents",
            }
        )
    for item in contract.boq_items():
        rows.append(
            {
                "id": f"boq-{item.get('item_code')}",
                "source": contract.boq_document_id(),
                "kind": "boq_item",
                "ref": str(item.get("item_code")),
                "label": f"{item.get('item_code')} {item.get('description', '')}".strip(),
                "text": (
                    f"{item.get('description')} - {item.get('quantity')} "
                    f"{item.get('unit')} at {item.get('rate')}"
                ),
                "authority_layer": "documents",
            }
        )
    return rows


class Index:
    """A small in-memory BM25 index; rebuilt when the documents change."""

    def __init__(self, rows: Iterable[Dict[str, Any]]):
        self.rows = list(rows)
        self.doc_tokens = [(_tokens(row["text"] + " " + row["label"]), row) for row in self.rows]
        self.df: Dict[str, int] = {}
        for tokens, _row in self.doc_tokens:
            for word in set(tokens):
                self.df[word] = self.df.get(word, 0) + 1
        self.avg_len = (
            sum(len(tokens) for tokens, _ in self.doc_tokens) / len(self.doc_tokens)
            if self.doc_tokens
            else 0.0
        )

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        terms = _tokens(query)
        if not terms or not self.doc_tokens:
            return []
        total = len(self.doc_tokens)
        scored = []
        for tokens, row in self.doc_tokens:
            counts: Dict[str, int] = {}
            for word in tokens:
                counts[word] = counts.get(word, 0) + 1
            score = 0.0
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (total - self.df.get(term, 0) + 0.5) / (self.df.get(term, 0) + 0.5))
                length = max(len(tokens), 1)
                score += idf * (frequency * 2.2) / (
                    frequency + 1.2 * (0.25 + 0.75 * length / max(self.avg_len, 1.0))
                )
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {**row, "score": round(score, 4)}
            for score, row in scored[: max(1, int(limit))]
        ]


_INDEX: Index | None = None
_INDEX_LEN = -1


def index() -> Index:
    global _INDEX, _INDEX_LEN
    rows = passages()
    if _INDEX is None or len(rows) != _INDEX_LEN:
        _INDEX = Index(rows)
        _INDEX_LEN = len(rows)
    return _INDEX


def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    return index().search(query, limit=limit)


def best_grounding(query: str) -> Dict[str, Any] | None:
    hits = search(query, limit=1)
    return hits[0] if hits else None
