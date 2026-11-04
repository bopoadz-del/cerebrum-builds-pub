"""library_surfaces -- each week's readings, sources, and the case reveal rule.

A week's library shows the readings and public sources that session needs. Case
OUTCOMES are different: they stay withheld until the case_class session, so a
learner cannot read the ending before the discussion. Anything an operator has
ingested into the tenant corpus is searchable here too, through real retrieval
-- the library is empty until the customer supplies sources.

READS   the track file for the week, the tenant's ingested corpus, the query.
WRITES  the reading list, retrieved sources and their authority labels.
NEVER   reveals a case outcome outside the case_class session, or invents a
        source the corpus does not hold (an empty corpus returns empty).
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import authority, block_inputs, retrieval, tracks
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "library_surfaces"
ENTITY = "library_surfaces"
BLOCK_IDS = ["reference_corpus", "search", "knowledge", "vector_search"]

PUBLIC_SOURCES = [
    "Harvard Business Review archive",
    "The Economist (public articles)",
    "Company filings and annual reports",
]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    tenant = block_inputs.tenant_scope(record)
    track_key = _support.text_of(record, "track_key").lower() or "coo"
    week = max(1, min(16, _support.int_of(record, "week", 1) or 1))
    session_kind = _support.text_of(record, "session_kind").lower()
    query = _support.text_of(record, "query") or f"week {week} {track_key}"
    tenant_id = str(record.get("_tenant_id") or "")

    document = tracks.seed(track_key) or {}
    detail = tracks.week_detail(document, week)
    readings = list(detail.get("readings") or []) or [f"Reading pack, week {week}"]
    case = str(detail.get("case") or "")

    # The case outcome is revealed ONLY in the case_class session.
    reveal = session_kind == "case_class"
    case_block = {
        "case": case,
        "outcome": detail.get("outcome") if reveal else None,
        "revealed": reveal,
        "reveal_rule": "case outcomes are revealed in the case_class session only",
    }

    retrieved: List[Dict[str, Any]] = []
    if tenant_id and query:
        try:
            retrieved = retrieval.search(query, tenant_id, limit=5)
        except Exception:  # noqa: BLE001 - an empty corpus is not a refusal
            retrieved = []

    inputs: Dict[str, Dict[str, Any]] = {
        "reference_corpus": {
            "project_id": tenant,
            "track_key": track_key,
            "week": week,
            "readings": readings,
            "sources": PUBLIC_SOURCES,
            "corpus": [{"title": item, "kind": "reading"} for item in readings],
            "query": query,
        },
        "search": {
            "query": query,
            "provider": "mock",
            "collections": ["readings", "cases"],
            "limit": 5,
            "filters": {"track_key": track_key, "week": week},
        },
        "knowledge": {
            "query": query,
            "question": query,
            "project_id": tenant,
            "top_k": 5,
            "topic": f"{track_key} week {week}",
            "week": week,
            "readings": readings,
        },
        "vector_search": {
            "query": query,
            "top_k": 5,
            "namespace": tenant_id or "library",
            "documents": [{"text": item, "title": item} for item in readings],
            "reference": reference,
        },
    }
    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    result = {
        "reference": reference,
        "track_key": track_key,
        "week": week,
        "theme": detail.get("theme") or f"Week {week}",
        "readings": readings,
        "public_sources": PUBLIC_SOURCES,
        "case": case_block,
        "retrieved": retrieved,
        "citations": [hit.get("citation") for hit in retrieved],
        "corpus_size": len(retrieved),
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(2 if retrieved else 1),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
