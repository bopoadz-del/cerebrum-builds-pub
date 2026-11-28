"""Retrieval over stored records, with authority labels.

There is no seeded corpus: a document store is empty until the operator
supplies sources.  Retrieval ranks the tenant's own records by token overlap
and every hit carries the layer it came from.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app import store

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_TOKEN.findall(str(text or "").lower()))


def search(entity: str, query: str, tenant_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    wanted = _tokens(query)
    scored = []
    for record in store.list_all(entity, tenant_id=tenant_id):
        haystack = _tokens(" ".join(str(v) for v in record.values() if isinstance(v, (str, int, float))))
        overlap = len(wanted & haystack)
        if wanted and overlap == 0:
            continue
        scored.append({
            "record": record,
            "score": overlap,
            "authority": {"label": "documents", "layer": 2, "basis": "stored record"},
        })
    scored.sort(key=lambda hit: (-hit["score"], hit["record"].get("id") or 0))
    return scored[: max(0, int(limit))]
