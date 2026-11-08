"""contract_and_boq_source_of_record -- the governing term, held as record.

One record resolves exactly one governing term: a contract clause or a BOQ
line. The term is cited as ``document:<filename>`` and the platform refuses a
clause number or BOQ item the uploaded documents do not contain, rather than
answering from a guess.

READS   the request record, corpus/source_of_record.json, the parsed contract
        PDF and the BOQ CSV derived from the same source.
WRITES  the resolved term and the parsed document text under
        STORAGE_PATH/workspace; the ROUTE persists the record, never this
        handler.
NEVER   invents a clause, a BOQ quantity or a rate the documents do not state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from app import contract_data
from app import capability_support as _support
from app.capability_support import ok, refuse, run_blocks
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "contract_and_boq_source_of_record"
ENTITY = "contract_and_boq_source_of_record"
BLOCK_IDS = ["document_engine", "pdf", "validation", "audit_chain"]
BLOCK_DEFAULT_ACTIONS = {
    block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS
}


def _pdf_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_pdf(path: Path, lines: List[str]) -> Path:
    """Materialise the cited text as a small one-page PDF for the pdf block."""
    content = ["BT", "/F1 9 Tf", "36 806 Td"]
    for index, line in enumerate(lines[:56]):
        if index:
            content.append("0 -13 Td")
        content.append(f"({_pdf_escape(line[:118])}) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return path


def _resolve_contract(record: Dict[str, Any], reference: str) -> Tuple[Dict[str, Any], str]:
    clause_ref = _support.text_of(record, "clause_ref")
    if clause_ref:
        governing = contract_data.clause(clause_ref)
        if governing is None:
            raise LookupError(
                f"Clause {clause_ref} is not in the uploaded contract; known clauses: "
                + ", ".join(sorted(contract_data.CLAUSES))
            )
        resolved = {
            "source_document": contract_data.CONTRACT_DOCUMENT,
            "document_type": "contract",
            "clause_ref": clause_ref,
            "boq_item": "",
            "description": _support.text_of(record, "description") or governing["text"],
            "unit": "",
            "quantity": 0.0,
            "rate": 0.0,
            "amount": 0.0,
            "citation": governing["document"],
        }
        return resolved, governing["text"]
    # No clause named: the whole contract is the term held in the register.
    text = contract_data.contract_source_text()
    resolved = {
        "source_document": contract_data.CONTRACT_DOCUMENT,
        "document_type": "contract",
        "clause_ref": "",
        "boq_item": "",
        "description": _support.text_of(record, "description") or text,
        "unit": "",
        "quantity": 0.0,
        "rate": 0.0,
        "amount": 0.0,
        "citation": contract_data.CONTRACT_DOCUMENT,
    }
    return resolved, text


def _resolve_boq(record: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    code = _support.text_of(record, "boq_item").upper()
    line = contract_data.boq_item(code)
    if line is None:
        raise LookupError(
            f"BOQ item {code or '(none)'} is not in the uploaded BOQ; known items: "
            + ", ".join(row["item"] for row in contract_data.boq_lines())
        )
    quantity = _support.number_of(record, "quantity", 0.0) or float(line["quantity"])
    rate = _support.number_of(record, "rate", 0.0) or float(line["rate"])
    resolved = {
        "source_document": contract_data.BOQ_DOCUMENT,
        "document_type": "boq",
        "clause_ref": "",
        "boq_item": line["item"],
        "description": _support.text_of(record, "description") or line["description"],
        "unit": _support.text_of(record, "unit") or line["unit"],
        "quantity": quantity,
        "rate": rate,
        "amount": round(quantity * rate, 2),
        "citation": line["document"],
    }
    text = (
        f"{line['item']} {line['description']} -- {quantity} {line['unit']} "
        f"at {rate}; amount {resolved['amount']}"
    )
    return resolved, text


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    input_digest = _support.input_digest(record)
    reference = _support.reference_of(record)
    document_type = (_support.text_of(record, "document_type") or "").lower()
    if not document_type:
        # A bare schema-sample record names no term; hold the contract itself
        # as the source of record rather than inventing a clause.
        document_type = "boq" if _support.text_of(record, "boq_item") else "contract"

    try:
        if document_type == "boq":
            resolved, text = _resolve_boq(record)
        elif document_type == "contract":
            resolved, text = _resolve_contract(record, reference)
        else:
            return refuse(
                "document_type must name a document in the source of record (contract or boq)",
                error_kind="invalid_document_type",
                input_digest=input_digest,
            )
    except LookupError as exc:
        return refuse(str(exc), error_kind="governing_term_missing", input_digest=input_digest)

    workspace = _support.workspace_dir(CAPABILITY_ID)
    stem = input_digest[:12]
    try:
        pdf_path = _write_pdf(workspace / f"source_{stem}.pdf", text.splitlines())
    except OSError:
        pdf_path = None
    try:
        boq_csv = contract_data.write_boq_csv(workspace, f"boq_{stem}")
    except OSError:
        boq_csv = None

    item = {
        "id": reference,
        "type": resolved["document_type"],
        "unit": resolved["unit"] or None,
        "source": resolved["citation"],
    }
    inputs: Dict[str, Dict[str, Any]] = {
        "document_engine": {"brief": text},
        "pdf": {"file_path": str(pdf_path) if pdf_path is not None else ""},
        "validation": {"item": item, "context": {"source": resolved["citation"]}},
        "audit_chain": {
            "tenant_id": _support.text_of(record, "_tenant_id") or "local",
            "action_execution_id": f"source-{stem}",
            "action_type": "source_of_record_resolved",
            "principal_id": _support.text_of(record, "_principal_id", "principal_id") or "document-controller",
            "payload": resolved,
            "result": {"reference": reference, "citation": resolved["citation"]},
        },
    }
    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused", input_digest=input_digest)

    artifact = {**resolved, "reference": reference}
    _support.write_artifact(workspace, f"source_{stem}.json", artifact)
    result = {
        **resolved,
        "reference": reference,
        "clause_terms": contract_data.clause(resolved["clause_ref"]) if resolved["clause_ref"] else None,
        "boq_total": contract_data.boq_total(),
        "source_file": _support.artifact_name("source", artifact),
        "block_evidence": {
            "document_parsed": isinstance(answers.get("document_engine"), dict)
            and answers["document_engine"].get("ok") is not False,
            "pdf_parsed": isinstance(answers.get("pdf"), dict)
            and answers["pdf"].get("ok") is not False,
            "validated": isinstance(answers.get("validation"), dict)
            and answers["validation"].get("ok") is not False,
            "chained": isinstance(answers.get("audit_chain"), dict)
            and answers["audit_chain"].get("ok") is not False,
        },
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 2 documents",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result, input_digest=input_digest)
