"""Lexical retrieval over the tenant's own source-of-record records.

The platform has no external vector service and no network. Retrieval reads
the persisted contract/BOQ source records and the controlled document register
for one tenant and ranks them by token overlap. Every hit names the record and
the source document it cites, so an operator can trace the passage back.

READS   app.store.list_all for the tenant.
WRITES  nothing.
NEVER   invents a passage, a document or a tenant: an empty tenant gets no hits.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app import store

MAX_HITS = 5
SEARCHED_ENTITIES = ("contract_terms_governance", "document_register", "progress_claim_management")
_STOPWORDS = frozenset(
    "the a an of and or to in for on at by is are was were be been with from as it its this that these those".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> List[str]:
    return [token for token in _TOKEN.findall(str(text or "").lower()) if token not in _STOPWORDS]


def _entity_text(entity: str, row: Dict[str, Any]) -> str:
    parts = [entity.replace("_", " ")]
    for key in ("reference", "description", "title", "clause_ref", "boq_item", "document_type", "source_document"):
        value = row.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    return " ".join(parts)


def search(question: str, tenant_id: str, limit: int = MAX_HITS) -> Dict[str, Any]:
    terms = set(tokens(question))
    if not terms:
        return {"query": question, "hits": [], "total": 0}
    scored: List[Dict[str, Any]] = []
    for entity in SEARCHED_ENTITIES:
        try:
            rows = store.list_all(entity, tenant_id=tenant_id)
        except KeyError:
            continue
        for row in rows:
            text = _entity_text(entity, row)
            overlap = terms & set(tokens(text))
            if not overlap:
                continue
            scored.append(
                {
                    "entity": entity,
                    "id": row.get("id"),
                    "text": text,
                    "reference": row.get("reference"),
                    "source": row.get("source_document") or row.get("citation"),
                    "score": round(len(overlap) / float(len(terms)), 4),
                    "matched": sorted(overlap),
                }
            )
    scored.sort(key=lambda row: (-row["score"], str(row.get("entity")), row.get("id") or 0))
    hits = scored[: max(1, int(limit))]
    return {"query": question, "hits": hits, "total": len(hits)}


def citations(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "entity": hit.get("entity"),
            "id": hit.get("id"),
            "reference": hit.get("reference"),
            "source": hit.get("source"),
            "score": hit.get("score"),
        }
        for hit in hits
    ]
