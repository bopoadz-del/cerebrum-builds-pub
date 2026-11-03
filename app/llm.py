"""Offline answering over the tenant's own evidence.

No provider is called: the answer is composed from the registered
documents and the contract clauses that retrieval found. That is the
honest design for an offline platform -- the text an operator reads is
always traceable to a row they registered or a clause of the uploaded
contract, never generated prose with no source.

An answer with no evidence is REFUSED (``ok: false``), never invented.
Every answer carries its authority label and its citations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app import authority, retrieval

MAX_CITATIONS = 5


def _sentences(text: str, terms: set) -> List[str]:
    parts = [part.strip() for part in str(text or "").split(". ") if part.strip()]
    return [part for part in parts if terms & set(retrieval.tokenise(part))]


def answer(question: str, tenant_id: str, limit: int = MAX_CITATIONS) -> Dict[str, Any]:
    """Answer a question from the contract text and the registered documents.

    Returns ``{ok, answer, authority, citations, divergences}``; an empty
    evidence set returns ``ok: false`` with the reason, because a platform
    that answers a contract question from nothing is the failure mode this
    product exists to prevent.
    """
    terms = set(retrieval.tokenise(question))
    if not terms:
        return {
            "ok": False,
            "error": "a question with no searchable terms cannot be answered",
            "authority": authority.label(2),
            "citations": [],
        }

    citations: List[Dict[str, Any]] = []
    for clause in retrieval.clauses(question):
        citations.append(
            {
                "kind": "contract_clause",
                "clause": clause["clause"],
                "text": clause["text"],
                "source": authority.CONTRACT_SOURCE,
            }
        )
    for hit in retrieval.search(question, tenant_id=tenant_id, limit=limit):
        citations.append(
            {
                "kind": "registered_document",
                "reference": hit.get("reference"),
                "title": hit.get("title"),
                "revision": hit.get("revision"),
                "source": hit.get("source_filename"),
                "score": hit.get("score"),
            }
        )
    citations = citations[:limit]

    if not citations:
        return {
            "ok": False,
            "error": "no evidence in the contract excerpt or the document register answers this question",
            "authority": authority.label(2),
            "citations": [],
        }

    excerpts: List[str] = []
    for citation in citations:
        if citation.get("kind") == "contract_clause":
            excerpts.append(str(citation.get("text") or ""))
        else:
            text = " ".join(
                str(citation.get(key) or "")
                for key in ("title", "reference", "revision", "document_type")
            ).strip()
            excerpts.append(text)
    body = " ".join(part for part in excerpts if part).strip()

    resolved = authority.resolve(
        [
            authority.Claim(2, body, authority.CONTRACT_SOURCE),
        ]
    )
    return {
        "ok": True,
        "answer": body,
        "authority": resolved["authority"],
        "citations": citations,
        "divergences": resolved["divergences"],
        "precedence": resolved["precedence"],
    }
