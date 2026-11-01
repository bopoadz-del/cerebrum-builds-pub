"""Tenant-scoped document retrieval. Ingest and query stay tenant-isolated."""

from __future__ import annotations

from typing import Any, Dict, List

_CORPUS: Dict[str, List[Dict[str, Any]]] = {}


def reset() -> None:
    _CORPUS.clear()


def ingest(tenant_id: str, document_name: str, text: str, source_kind: str = "sop",
           authority: str = "documents") -> Dict[str, Any]:
    tenant = str(tenant_id)
    entry = {
        "document_name": str(document_name),
        "source_kind": str(source_kind),
        "text": str(text or ""),
        "citation": f"{document_name}",
        "authority": str(authority),
        "tenant_id": tenant,
    }
    _CORPUS.setdefault(tenant, []).append(entry)
    return {"ingested": True, "document_name": entry["document_name"],
            "tenant_id": tenant, "chars": len(entry["text"])}


def documents(tenant_id: str) -> List[Dict[str, Any]]:
    return [
        {"document_name": d["document_name"], "source_kind": d["source_kind"],
         "citation": d["citation"], "authority": d["authority"]}
        for d in _CORPUS.get(str(tenant_id), [])
    ]


def search(tenant_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    terms = [t for t in str(query or "").lower().split() if t]
    out: List[Dict[str, Any]] = []
    for doc in _CORPUS.get(str(tenant_id), []):
        text = doc["text"]
        low = text.lower()
        score = sum(low.count(t) for t in terms)
        if not terms or score:
            out.append({
                "document_name": doc["document_name"],
                "citation": doc["citation"],
                "authority": doc["authority"],
                "score": score,
                "snippet": text[:400],
            })
    out.sort(key=lambda d: d["score"], reverse=True)
    return out[:limit]
