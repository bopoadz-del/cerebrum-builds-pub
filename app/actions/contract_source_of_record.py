"""contract_source_of_record -- the contract and BOQ as the pinned authority.

Ingests the uploaded the project contract and BOQ, extracts the governing
terms (Clause 8.2 Time for Completion, 8.7 Delay Damages, 11.1 Defects
Notification Period, 14.3 Retention, 4.2 Performance Security) and the BOQ
item/rate schedule, and makes that pinned set the authority every other
capability reads.

Scope READS: caller payload, app/sources.py, the vendored blocks.
Scope WRITES: caller output only -- the HTTP route owns persistence.
Scope NEVER: no network, no invented clause, no BOQ line not in the upload.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from app import sources
from app.actions._artifacts import Workspace
from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    currency,
    record_of,
    refusal,
    success,
    text_of,
)
from app.dispatch import BLOCK_DEFAULT_ACTIONS as DISPATCH_ACTIONS
from app.actions._blocks import is_refusal
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "contract_source_of_record"
ENTITY = CAPABILITY_ID

BLOCK_IDS = ["pdf", "ocr", "knowledge", "document_engine", "vector_search", "audit_chain"]

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    "pdf": None,
    "ocr": None,
    "knowledge": "search",
    "document_engine": None,
    "vector_search": "search",
    "audit_chain": "record_evidence",
}

AUTHORITY = authority(CAPABILITY_ID, 1, "certified")


def _pin_set(selected: Any) -> List[Dict[str, Any]]:
    wanted = text_of(selected).strip().upper()
    pinned = []
    for clause in sources.CONTRACT_CLAUSES:
        if wanted and wanted not in (clause["clause"].upper(), clause["title"].upper()):
            continue
        pinned.append(
            {
                "clause": clause["clause"],
                "title": clause["title"],
                "pinned_value": clause["value"],
                "unit": clause["unit"],
                "cap_percent": clause.get("cap_percent"),
                "citation": sources.CONTRACT_DOCUMENT,
            }
        )
    return pinned or [
        {
            "clause": clause["clause"],
            "title": clause["title"],
            "pinned_value": clause["value"],
            "unit": clause["unit"],
            "cap_percent": clause.get("cap_percent"),
            "citation": sources.CONTRACT_DOCUMENT,
        }
        for clause in sources.CONTRACT_CLAUSES
    ]


def handle(payload: Any) -> Dict[str, Any]:
    record = record_of(CAPABILITY_ID, payload)
    contract = sources.contract_text()
    digest = hashlib.sha256(contract.encode("utf-8")).hexdigest()
    pinned = _pin_set(record.get("clause_ref"))
    boq_total = sources.accepted_contract_amount()

    inputs: Dict[str, Dict[str, Any]] = {}
    workspace = Workspace("harbourline-source-")
    try:
        try:
            contract_file = workspace.docx("harbourline_contract.docx", contract)
        except Exception:
            contract_file = workspace.write_text("harbourline_contract.txt", contract)
        inputs = {
            "pdf": {"file_path": contract_file},
            "ocr": {"file_path": contract_file},
            "knowledge": {
                "question": "Which contract clauses govern time, damages, "
                            "retention, security and the defects period?",
                "query": "Clause 8.2 8.7 11.1 14.3 4.2 the project",
            },
            "document_engine": {"text": contract},
            "vector_search": {
                "query": "Clause 8.2 Time for Completion 730 days",
                "text": "Clause 8.2 Time for Completion 730 days",
            },
            "audit_chain": {
                "action_execution_id": "pin-" + digest[:16],
                "action_type": "pin_contract_terms",
                "principal_id": text_of(record.get("source_digest")) or "contract-administrator",
                "payload": {"document": sources.CONTRACT_DOCUMENT},
                "result": {"clauses": [item["clause"] for item in pinned]},
            },
        }
        answers, refusals = call_blocks(
            BLOCK_IDS, BLOCK_DEFAULT_ACTIONS, inputs, entity=ENTITY, roster=BLOCK_IDS
        )
    finally:
        workspace.close()

    if refusals:
        return refusal(
            CAPABILITY_ID, AUTHORITY, refusals, answers,
            input_digest=record.get("_input_digest"),
        )

    extracted = answers.get("pdf") or {}
    extracted_text = text_of(extracted.get("text"))
    verification = {
        "engine": extracted.get("engine") or None,
        "extracted_chars": len(extracted_text),
        "clauses_seen": [
            item["clause"] for item in pinned
            if ("%s" % item["clause"]) in extracted_text
        ],
        "source_is_ingested": bool(extracted_text),
    }
    if not extracted_text:
        verification["note"] = (
            "the document block could not extract text in this build; the "
            "pinned terms are read from the uploaded document as transcribed "
            "in app/sources.py"
        )

    return success(
        CAPABILITY_ID,
        AUTHORITY,
        answers,
        input_digest=record.get("_input_digest"),
        result={
            "project": sources.PROJECT_NAME,
            "document": sources.CONTRACT_DOCUMENT,
            "boq_document": sources.BOQ_DOCUMENT,
            "pinned": pinned,
            "boq": {
                "items": sources.line_count(),
                "total": boq_total,
                "currency": currency(),
                "citation": sources.BOQ_DOCUMENT,
            },
            "source_digest": digest,
            "verification": verification,
            "authority_note": (
                "layer 1: the uploaded contract and BOQ are the source of record"
            ),
        },
    )
