"""Answers manager questions grounded in uploaded plant documents."""

from __future__ import annotations

from typing import Any, Dict

from app import llm, retrieval
from app.actions._common import block_failure, envelope
from app.authority import authority
from app.dispatch import execute
from app.cerebrum_product_kernel.claim_labels import Citation, Claim, LabeledAnswer
from app.tenancy import current_tenant

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_grounded_qa"
ENTITY = "document_grounded_qa"
BLOCK_IDS = ["vector_search", "search", "llm_enhancer"]
BLOCK_DEFAULT_ACTIONS = {"vector_search": None, "search": None, "llm_enhancer": "status"}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "database", "scope": "tenant_corpus"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    question = str(record.get("question") or "summarize the uploaded plant documents")
    try:
        top_k = int(record.get("top_k") or 5)
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(20, top_k))

    vector = execute(
        "vector_search",
        {"query": question},
        action=BLOCK_DEFAULT_ACTIONS.get("vector_search"),
        params={"operation": "search", "collection": "plant_documents"},
    )
    refused = block_failure("vector_search", vector)
    if refused:
        return refused

    web = execute(
        "search",
        question,
        action=BLOCK_DEFAULT_ACTIONS.get("search"),
        params={"provider": "mock"},
    )
    refused = block_failure("search", web)
    if refused:
        return refused

    enhancer = execute(
        "llm_enhancer",
        {},
        action=BLOCK_DEFAULT_ACTIONS.get("llm_enhancer"),
    )
    refused = block_failure("llm_enhancer", enhancer)
    if refused:
        return refused

    hits = retrieval.search(question, top_k=top_k, tenant_id=current_tenant())
    sources = retrieval.citations(hits)
    synthesis = llm.synthesize(question, hits)
    answer_authority = authority(2, source=sources[0]["document_name"] if sources else "no_source")
    claims = [
        Claim(
            text=str(source.get("text") or ""),
            layer=2,
            object_id="%s:%s" % (source.get("document_id"), source.get("chunk_index")),
        )
        for source in sources
    ]
    citations = [
        Citation(
            file=str(source.get("document_name") or ""),
            location={"chunk": source.get("chunk_index"), "source": source.get("source")},
        )
        for source in sources
    ]
    labeled = LabeledAnswer(claims=claims, citations=citations).to_dict()
    return envelope(
        {
            "question": question,
            "answer": synthesis["answer"],
            "confidence": synthesis["confidence"],
            "sources": sources,
            "authority": answer_authority,
            "claims": labeled["claims"],
            "citations": labeled["citations"],
            "divergence": [],
            "retrieval": {
                "vector_store_hits": len(vector.get("results") or []),
                "external_search_provider": "mock" if not str(question).startswith("http") else "web",
                "external_search_hits": len(web.get("results") or []),
                "corpus_matches": len(hits),
                "enhancer_active": bool(enhancer.get("is_active")),
            },
        },
        record,
    )
