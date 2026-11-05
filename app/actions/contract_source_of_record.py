"""contract_source_of_record -- the contract excerpt and BOQ as source of record.

A record pins one clause or BOQ line to the document it came from. Every later
claim, inspection and certificate cites that document id instead of restating
(or inventing) a rate, so the uploaded contract and BOQ remain the single
source of record for the project.

READS   the request record, the uploaded contract/BOQ data shipped in
        ``app/contract_data.py``, and the workspace files it materialises.
WRITES  a BOQ extract under STORAGE_PATH/workspace and this capability's
        result; the ROUTE persists the record, never the handler.
NEVER   invents a clause, a rate or a quantity; accepts an unknown BOQ item as
        a citable record only when the caller supplies its own description.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from app import contract_data
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks
from app.block_inputs import prepare_block_input
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "contract_source_of_record"
ENTITY = "contract_source_of_record"
BLOCK_IDS = ["document_engine", "ocr", "pdf", "storage", "knowledge", "ingestion_provenance"]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}


def _ocr_image(directory, text: str, stem: str = "contract_clause_scan"):
    """A plain scan-like image of the clause text for the local OCR engine."""
    try:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (1400, 420), "white")
        draw = ImageDraw.Draw(image)
        lines = [line for line in str(text).splitlines() if line.strip()][:12]
        for index, line in enumerate(lines):
            draw.text((30, 24 + index * 30), line[:110], fill="black")
        path = directory / (str(stem) + ".png")
        image.save(path, "PNG")
        return path
    except Exception:  # noqa: BLE001 - the OCR block reports its own refusal
        return None


def _source_document(record: Dict[str, Any]) -> str:
    declared = _support.text_of(record, "source_document")
    if declared:
        return declared
    if _support.text_of(record, "document_type").lower() == "boq":
        return contract_data.BOQ_DOCUMENT
    return contract_data.CONTRACT_DOCUMENT


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    document_type = (_support.text_of(record, "document_type") or "contract").lower()
    source_document = _source_document(record)
    clause_ref = _support.text_of(record, "clause_ref")
    boq_item = _support.text_of(record, "boq_item").upper()

    line = contract_data.boq_item(boq_item) if boq_item else None
    quantity = _support.number_of(record, "quantity", 0.0)
    rate = _support.number_of(record, "rate", 0.0)
    amount = _support.number_of(record, "amount", 0.0)
    if line and not quantity:
        quantity = float(line["quantity"])
    if line and not rate:
        rate = float(line["rate"])
    if not amount:
        amount = round(quantity * rate, 2)
    if line and not amount:
        amount = float(line["amount"])

    clause = contract_data.clause_text(clause_ref)
    if clause_ref and not clause:
        return refuse(
            f"clause_ref {clause_ref!r} is not in the uploaded contract excerpt; "
            "known clauses: " + ", ".join(sorted(contract_data.CLAUSES)),
            error_kind="unknown_clause",
        )
    if boq_item and line is None:
        return refuse(
            f"boq_item {boq_item!r} is not in the uploaded BOQ; known items: "
            + ", ".join(item["item"] for item in contract_data.boq_lines()),
            error_kind="unknown_boq_item",
        )

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = f"boq_{uuid.uuid4().hex[:12]}"
    boq_csv = contract_data.write_boq_csv(workspace, stem)
    boq_xlsx = contract_data.write_boq_xlsx(workspace, stem)
    body = contract_data.record_text(
        {
            "reference": reference,
            "source_document": source_document,
            "document_type": document_type,
            "clause": clause_ref,
            "clause_text": clause,
            "boq_item": boq_item,
            "description": _support.text_of(record, "description") or (line or {}).get("description", ""),
            "quantity": quantity,
            "rate": rate,
            "amount": amount,
            "currency": "SAR",
        }
    )
    scan_image = _ocr_image(workspace, body, f"scan_{uuid.uuid4().hex[:12]}")
    content_file = workspace / f"source_{reference.replace('/', '_')}_{uuid.uuid4().hex[:8]}.json"
    content_file.write_text(
        json.dumps(
            {
                "reference": reference,
                "source_document": source_document,
                "document_type": document_type,
                "clause_ref": clause_ref,
                "boq_item": boq_item,
                "quantity": quantity,
                "rate": rate,
                "amount": amount,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {
            "brief": f"Extract the clause and BOQ obligations for {reference}:\n{body}",
        },
        "ocr": {"file_path": str(scan_image or boq_xlsx)},
        "pdf": {"file_path": str(boq_xlsx)},
        "storage": {
            "content": body,
            "filename": content_file.name,
            "metadata": {"reference": reference, "source_document": source_document},
        },
        "knowledge": {
            "query": f"Which clause governs {clause_ref or boq_item or reference} in the Harbourline contract?",
            "text": contract_data.contract_source_text(),
        },
        "ingestion_provenance": {
            "source": source_document,
            "labels": [document_type, "harbourline"],
            "records": [{"reference": reference, "source_document": source_document}],
            "text": body,
        },
    }

    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result: Dict[str, Any] = {
        "reference": reference,
        "source_of_record": True,
        "source_document": source_document,
        "document_type": document_type,
        "clause_ref": clause_ref,
        "clause_text": clause,
        "boq_item": boq_item,
        "boq_section": (line or {}).get("section"),
        "description": (line or {}).get("description") or _support.text_of(record, "description"),
        "unit": (line or {}).get("unit") or _support.text_of(record, "unit"),
        "quantity": quantity,
        "rate": rate,
        "amount": amount,
        "currency": "SAR",
        "accepted_contract_amount": contract_data.boq_total(),
        "citation": source_document,
        "blocks_run": list(BLOCK_IDS),
        "boq_extract": str(boq_csv),
        "document_text_extracted": bool(
            isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False
        ),
        "authority": "layer 2 documents",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
