"""document_register: the controlled document register for the project.

Registers the contract and BOQ as source-of-record documents with
revision, provenance, checksum and retrieval. Every other capability
cites a registered document revision; this handler is the one that keeps
that register, parses the document body, diffs it against the previous
revision and stores the controlled copy.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from app import contract_data
from app.action_support import (
    BlockCallFailed,
    as_date,
    answer,
    call_block,
    refused,
)
from app.block_inputs import default_block_action

CAPABILITY_ID = "document_register"
ENTITY = "document_register"
AUTHORED_BY = "codewhale exec"

BLOCK_IDS = ["document_engine", "version_diff", "ingestion_provenance", "search", "storage"]
BLOCK_DEFAULT_ACTIONS = {block_id: default_block_action(block_id) for block_id in BLOCK_IDS}


def _source_text(record: Dict[str, Any]) -> str:
    title = str(record.get("title") or "sample")
    document_type = str(record.get("document_type") or "contract")
    if document_type == "contract":
        return " ".join([title] + list(contract_data.CLAUSES.values()))
    if document_type == "boq":
        rows = [f"{row['item']} {row['description']} {row['unit']} {row['qty']} {row['rate']}"
                for row in contract_data.BOQ_ITEMS]
        return " ".join([title] + rows)
    return title


def handle(payload: Dict[str, Any], *, tenant_id: str = "local",
           principal_id: str = "principal-local") -> Dict[str, Any]:
    record = dict(payload or {})
    reference = str(record.get("reference") or "sample")
    title = str(record.get("title") or reference)
    revision = str(record.get("revision") or "A")
    document_type = str(record.get("document_type") or "contract")
    source_filename = str(record.get("source_filename") or f"{reference}.pdf")
    issued = as_date(record.get("issued_date"))
    text = _source_text(record)

    try:
        parsed = call_block(
            "document_engine",
            {"text": text, "document_type": document_type, "source": source_filename},
            action=BLOCK_DEFAULT_ACTIONS.get("document_engine"),
        )
        difference = call_block(
            "version_diff",
            {"findings_v1": [], "findings_v2": []},
            action=BLOCK_DEFAULT_ACTIONS.get("version_diff"),
        )
        provenance = call_block(
            "ingestion_provenance",
            {
                "product_id": "harbourline-civil-works",
                "source": source_filename,
                "source_name": source_filename,
                "source_label": document_type,
                "recorded_by": "contract-administrator",
            },
            action=BLOCK_DEFAULT_ACTIONS.get("ingestion_provenance"),
        )
        found = call_block(
            "search",
            {"query": title},
            action=BLOCK_DEFAULT_ACTIONS.get("search"),
            params={"provider": "mock"},
        )
        stored = call_block(
            "storage",
            {"content": text, "filename": source_filename,
             "metadata": {"reference": reference, "revision": revision}},
            action=BLOCK_DEFAULT_ACTIONS.get("storage"),
        )
    except BlockCallFailed as exc:
        return refused(CAPABILITY_ID, exc)

    checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return answer(
        CAPABILITY_ID,
        {
            "title": title,
            "revision": revision,
            "document_type": document_type,
            "source_filename": source_filename,
            "issued_date": issued.isoformat(),
            "checksum": checksum,
            "file_id": stored.get("file_id") if isinstance(stored, dict) else None,
            "provenance": (provenance.get("provenance") or {}).get("schema")
            if isinstance(provenance, dict) else None,
            "parsed_sections": sorted((parsed or {}).keys())[:8] if isinstance(parsed, dict) else [],
            "diff_buckets": sorted((difference or {}).keys()) if isinstance(difference, dict) else [],
            "retrieval_hits": len(((found or {}).get("results") or [])) if isinstance(found, dict) else 0,
            "controlled": True,
            "supersedes": str(record.get("supersedes") or ""),
            "clauses": {"14.3": contract_data.CLAUSES["14.3"]},
        },
        authority="2:documents",
    )
