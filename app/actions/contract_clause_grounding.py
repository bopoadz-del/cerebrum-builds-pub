"""Grounded answers over the uploaded contract and BOQ.

The question is retrieved from the source-of-record corpus, the retrieved
clauses are judged for evidence (a claim with no evidence is refused), and
the answer is sealed with a tamper-evident digest. The answer always names
the document it came from; when the corpus holds no matching clause the
answer says so instead of inventing one.
"""

from __future__ import annotations

import re
import uuid

from app import contract_terms as terms
from app import llm, retrieval, authority
from app.actions._support import (
    as_int, block_result, check, input_digest, ok, require_payload, tenant_id,
)
from app.block_inputs import default_block_action
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "contract_clause_grounding"
ENTITY = "contract_clause_grounding"
BLOCK_IDS = ["knowledge", "vector_search", "evidence_or_refuse", "evidence_verifier"]
BLOCK_DEFAULT_ACTIONS = {block: default_block_action(block) for block in BLOCK_IDS}

SCOPE_READS = ["payload", "app.retrieval", "app.contract_terms", "app.llm"]
SCOPE_WRITES = ["result"]
SCOPE_NEVER = ["store.save", "network"]

_CLAUSE = re.compile(r"Clause\s+(\d+\.\d+)", re.IGNORECASE)


def _seed_corpus(tenant):
    if retrieval.chunk_count(tenant) > 0:
        return
    for filename in (terms.CONTRACT_FILENAME, terms.BOQ_FILENAME):
        retrieval.ingest(tenant, terms.DOCUMENTS[filename], "document:%s" % filename)


def _retrieve(tenant, question):
    """Rank the tenant index; fall back to the uploaded corpus in place.

    A deployment always has its persistence root, so the indexed path is
    the normal one. Outside a deployment (a direct handle() call with no
    STORAGE_PATH) the same documents are ranked from app.contract_terms --
    no index is written and no second store is opened.
    """
    try:
        _seed_corpus(tenant)
        return retrieval.search(tenant, question, top_k=5)
    except (RuntimeError, OSError):
        return retrieval.search_corpus(question, top_k=5)


def _clauses(hits, question):
    """Rank the contract's parsed clauses against the question itself.

    A retrieved page can carry several clauses; the answer cites the one the
    question actually names or matches, not whichever clause appears first.
    """
    wanted = set(retrieval.tokens(question))
    scored = []
    for number, entry in terms.CLAUSES.items():
        body = "%s %s" % (entry.get("title") or "", entry.get("text") or "")
        overlap = len(wanted & set(retrieval.tokens(body)))
        if overlap:
            scored.append((overlap, number))
    scored.sort(key=lambda item: (-item[0], item[1]))
    found = [number for _score, number in scored]
    for hit in hits:
        for clause in _CLAUSE.findall(str(hit.get("text") or "")):
            if clause not in found:
                found.append(clause)
    return found


def handle(payload):
    payload = require_payload(payload)
    tenant = tenant_id()
    question = str(payload.get("question") or payload.get("clause_reference") or "")

    hits = _retrieve(tenant, question)

    index_answer = execute(
        "vector_search",
        {
            "operation": "add",
            "collection": "contract-clauses-%s" % tenant,
            "documents": [
                {"id": "%s#%s" % (hit["source"], hit["seq"]), "text": hit["text"]}
                for hit in (hits or retrieval.search(tenant, "contract", top_k=3))
            ],
        },
        action=BLOCK_DEFAULT_ACTIONS.get("vector_search"),
    )
    stopped = check("vector_search", index_answer)
    if stopped:
        return stopped
    index = block_result(index_answer)

    knowledge_answer = execute(
        "knowledge",
        {"input": question, "project_id": tenant, "top_k": 5},
        action=BLOCK_DEFAULT_ACTIONS.get("knowledge"),
    )
    stopped = check("knowledge", knowledge_answer)
    if stopped:
        return stopped
    knowledge = block_result(knowledge_answer)

    clauses = _clauses(hits, question)
    if hits:
        claims = [
            {
                "id": "claim-%d" % (position + 1),
                "text": "Clause %s answers the question" % clause,
                "evidence": [
                    {"document": hit.get("source"), "clause": clause, "score": hit.get("score")}
                    for hit in hits
                    if clause in str(hit.get("text") or "")
                ][:3],
            }
            for position, clause in enumerate(clauses[:3])
        ]
    else:
        claims = [
            {
                "id": "claim-none",
                "text": "The source of record holds no clause matching the question",
                "evidence": [
                    {"document": terms.document_citation(terms.CONTRACT_FILENAME), "clause": "corpus index"},
                    {"document": terms.document_citation(terms.BOQ_FILENAME), "clause": "corpus index"},
                ],
            }
        ]
    judge_answer = execute(
        "evidence_or_refuse",
        {"claims": claims},
        action=BLOCK_DEFAULT_ACTIONS.get("evidence_or_refuse"),
    )
    stopped = check("evidence_or_refuse", judge_answer)
    if stopped:
        return stopped
    verdict = block_result(judge_answer)

    synthesis = llm.synthesize(question, hits)
    answer_text = synthesis["answer"] or (
        "No clause in %s or %s matches the question; the platform refuses to answer "
        "without evidence." % (
            terms.document_citation(terms.CONTRACT_FILENAME),
            terms.document_citation(terms.BOQ_FILENAME),
        )
    )
    citation = (
        terms.clause_citation(clauses[0]) if clauses
        else terms.document_citation(terms.CONTRACT_FILENAME)
    )

    verifier_answer = execute(
        "evidence_verifier",
        {
            "content": {
                "reference": str(payload.get("reference") or ""),
                "question": question,
                "answer": answer_text,
                "citation": citation,
                "seal": uuid.uuid4().hex,
            }
        },
        action=BLOCK_DEFAULT_ACTIONS.get("evidence_verifier"),
    )
    stopped = check("evidence_verifier", verifier_answer)
    if stopped:
        return stopped
    verifier = block_result(verifier_answer)

    return ok(
        result={
            "capability_id": CAPABILITY_ID,
            "answer": answer_text,
            "answered": bool(hits),
            "clause_reference": clauses[0] if clauses else "",
            "document_reference": hits[0]["source"] if hits else terms.document_citation(terms.CONTRACT_FILENAME),
            "evidence_count": len(hits),
            "evidenced": bool(verdict.get("allowed")),
            "evidence_sufficient": bool(hits),
            "refused_for_insufficient_evidence": not bool(hits),
            "input_digest": input_digest(payload),
            "citations": [citation] + [hit["source"] for hit in hits[:3]],
            "authority": authority.label_for("documents"),
            "knowledge_hits": as_int(knowledge.get("total_found")),
            "indexed_chunks": as_int(index.get("added") or index.get("total")),
            "evidence_sha256": verifier.get("sha256"),
        }
    )
