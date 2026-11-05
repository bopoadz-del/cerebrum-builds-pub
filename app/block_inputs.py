"""Constructed block inputs.

Handlers feed the blocks they declare. The caller is never asked for a block's
own keys (file paths, record arrays, workflow steps); those are built here from
the domain record and the uploaded contract/BOQ source of record.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

from app import formulas
from app.dispatch import BLOCK_DEFAULT_ACTIONS, default_block_action

PROJECT_ID = "Harbourline Civil Works"


def contract_document() -> dict:
    for document in formulas.source_of_record().get("documents", []):
        if document.get("kind") == "contract":
            return document
    return {}


def boq_document() -> dict:
    for document in formulas.source_of_record().get("documents", []):
        if document.get("kind") == "boq":
            return document
    return {}


def cited(filename: str) -> str:
    return "document:" + str(filename)


def contract_citation() -> str:
    return cited(contract_document().get("filename", ""))


def boq_citation() -> str:
    return cited(boq_document().get("filename", ""))


def as_lines(value) -> list:
    """Accept a JSON list, a comma/semicolon string, or nothing."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    out = []
    for chunk in text.replace(";", ",").split(","):
        code, _, qty = chunk.strip().partition(":")
        if code:
            out.append({"item": code.strip(), "qty": qty.strip()})
    return out


def claim_lines(payload: dict) -> list:
    """The claim's quantities priced at the BOQ rate, or the full BOQ."""
    index = formulas.boq_index()
    supplied = as_lines((payload or {}).get("line_items")) or as_lines((payload or {}).get("boq_item_codes"))
    lines = []
    if supplied:
        for entry in supplied:
            code = str(entry.get("item") or entry.get("item_code") or entry.get("code") or "").strip()
            item = index.get(code)
            if item is None:
                continue
            qty = formulas.finite_number(entry.get("qty") or entry.get("quantity"), float(item["qty"]))
            rate = formulas.finite_number(entry.get("rate"), float(item["rate"]))
            lines.append({
                "item": code,
                "description": str(item["description"]),
                "unit": str(item["unit"]),
                "qty": qty,
                "rate": rate,
                "amount": formulas.money(qty * rate),
            })
    if not lines:
        for item in formulas.boq_items():
            lines.append({
                "item": str(item["item"]),
                "description": str(item["description"]),
                "unit": str(item["unit"]),
                "qty": float(item["qty"]),
                "rate": float(item["rate"]),
                "amount": formulas.money(float(item["qty"]) * float(item["rate"])),
            })
    return lines


def claimed_amount(payload: dict) -> float:
    supplied = formulas.finite_number((payload or {}).get("claimed_amount"), 0.0)
    if supplied > 0:
        return formulas.money(supplied)
    return formulas.money(sum(line["amount"] for line in claim_lines(payload)))


def boq_csv_path() -> str:
    """Write the uploaded BOQ as CSV for the block that parses bills."""
    directory = Path(tempfile.mkdtemp(prefix="harbourline-boq-"))
    path = directory / "harbourline_boq.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Description", "Unit", "Qty", "Rate", "Section"])
        for item in formulas.boq_items():
            writer.writerow([
                str(item["item"]) + " " + str(item["description"]),
                str(item["unit"]),
                item["qty"],
                item["rate"],
                str(item["section"]),
            ])
    return str(path)


def cleanup_path(path: str) -> None:
    try:
        os.unlink(path)
        os.rmdir(os.path.dirname(path))
    except OSError:
        pass


def finance_inputs(payload: dict) -> dict:
    left = [
        {"item": str(item["item"]), "amount": formulas.money(float(item["qty"]) * float(item["rate"]))}
        for item in formulas.boq_items()
    ]
    right = [
        {"item": str(line["item"]), "amount": float(line["amount"])}
        for line in claim_lines(payload)
    ]
    return {
        "left_records": left,
        "right_records": right,
        "group_by": ["item"],
        "amount_field": "amount",
        "tolerance": "0.01",
    }


def approval_inputs(payload: dict) -> dict:
    clauses = contract_document().get("clauses", [])
    extracted = [
        {
            "rule_id": "CLAUSE-" + str(clause.get("id")),
            "source_clause": str(clause.get("id")),
            "source_doc": contract_citation(),
            "text": str(clause.get("text")),
        }
        for clause in clauses
    ]
    return {
        "action": "ingest",
        "project_id": PROJECT_ID,
        "source_doc": contract_citation(),
        "extracted": extracted,
    }


def delay_values(payload: dict) -> dict:
    data = payload or {}
    accepted = formulas.finite_number(
        data.get("accepted_contract_amount") or data.get("claimed_amount"), formulas.boq_total()
    )
    days = int(formulas.finite_number(data.get("days_of_delay"), 0))
    if days <= 0:
        start = str(data.get("commencement_date") or "").strip()
        finish = str(data.get("actual_completion_date") or data.get("completion_date") or "").strip()
        if start and finish:
            try:
                from datetime import date

                allowed = int(
                    formulas.contract_clause("8.2").get("value") or 0
                )
                days = max(0, (date.fromisoformat(finish) - date.fromisoformat(start)).days - allowed)
            except ValueError:
                days = 0
    return {"accepted_contract_amount": accepted, "days_of_delay": days}


def delay_formula_inputs(payload: dict) -> dict:
    values = delay_values(payload)
    clause = formulas.contract_clause("8.7")
    return {
        "custom_code": formulas.delay_damages_code(),
        "formula_description": "Acceptance delay damages with Clause 8.7 cap",
        "input_values": {
            "accepted_contract_amount": values["accepted_contract_amount"],
            "daily_rate": float(clause.get("value") or 0.0),
            "days_of_delay": values["days_of_delay"],
            "cap_ratio": float(clause.get("cap_ratio") or 0.0),
        },
    }


def validation_inputs(payload: dict) -> dict:
    values = delay_values(payload)
    return {
        "item": {
            "id": str((payload or {}).get("reference") or "delay-position"),
            "type": "delay_event",
            "duration_days": values["days_of_delay"],
            "cost": values["accepted_contract_amount"],
        },
        "context": {"project_total_days": int(formulas.contract_clause("8.2").get("value") or 0)},
    }


def itp_text(payload: dict) -> str:
    data = payload or {}
    supplied = str(data.get("evidence_text") or data.get("notes") or "").strip()
    if supplied:
        return supplied
    code = str(data.get("boq_item_code") or "").strip()
    item = formulas.boq_index().get(code)
    description = item["description"] if item else "project works"
    return (
        "Inspection and Test Plan " + str(data.get("itp_number") or data.get("reference") or "ITP")
        + " for BOQ item " + (code or "not stated") + " (" + str(description) + "). "
        + "Inspection type: " + str(data.get("inspection_type") or "hold point") + ". "
        + "Requirement source: " + contract_citation() + " and " + boq_citation() + "."
    )


def document_text(payload: dict) -> str:
    data = payload or {}
    supplied = str(data.get("description") or "").strip()
    if supplied:
        return supplied
    return (
        "Controlled document " + str(data.get("title") or data.get("reference") or "register entry")
        + " of type " + str(data.get("document_type") or "specification")
        + ", revision " + str(data.get("revision") or "1.0.0") + ". "
        + "Source: " + str(data.get("source_document") or contract_citation()) + "."
    )


def document_search_query(payload: dict) -> str:
    data = payload or {}
    return str(data.get("search_query") or data.get("title") or data.get("reference") or "contract document")


def semver(value) -> str:
    text = str(value or "").strip()
    parts = [part for part in text.replace("-", ".").split(".") if part.isdigit()]
    if len(parts) >= 3:
        return ".".join(str(int(part)) for part in parts[:3])
    if len(parts) == 2:
        return ".".join([str(int(parts[0])), str(int(parts[1])), "0"])
    if len(parts) == 1:
        return ".".join([str(int(parts[0])), "0", "0"])
    return "1.0.0"


def prepare_block_input(block_id: str, capability_id: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    if capability_id == "progress_claim_administration":
        if block_id == "boq_processor":
            return {"file_path": boq_csv_path(), "currency": formulas.currency()}
        if block_id == "finance_reconciliation":
            return finance_inputs(payload)
        if block_id == "approval_rules":
            return approval_inputs(payload)
    if capability_id == "delay_damages_tracking":
        if block_id == "formula_executor":
            return delay_formula_inputs(payload)
        if block_id == "validation":
            return validation_inputs(payload)
    if capability_id == "qa_itp_records":
        if block_id == "document_engine":
            return {"text": itp_text(payload)}
        if block_id == "workflow":
            text = itp_text(payload)
            item = validation_inputs(payload)
            return {
                "pipeline_id": "qa-itp-" + str(payload.get("reference") or "record")[:32],
                "steps": [
                    {
                        "id": "step_0",
                        "block": "document_engine",
                        "input": {"text": text},
                        "params": {},
                    },
                    {
                        "id": "step_1",
                        "block": "document_engine",
                        "input": {"text": "QA/ITP acceptance: " + text},
                        "params": {},
                    },
                ],
                "result": rule_context(item),
            }
    if capability_id == "document_register":
        if block_id == "document_engine":
            return {"text": document_text(payload)}
        if block_id == "search":
            return {"query": document_search_query(payload)}
        if block_id == "version":
            return {
                "block_id": "document-register:" + str(payload.get("reference") or "entry")[:48],
                "version": semver(payload.get("revision")),
            }
    return {}


def rule_context(item: dict) -> dict:
    return {"item": item.get("item", {}), "capability": "qa_itp_records"}


def block_action(block_id: str) -> str | None:
    return default_block_action(block_id)


__all__ = [
    "BLOCK_DEFAULT_ACTIONS",
    "PROJECT_ID",
    "approval_inputs",
    "block_action",
    "boq_csv_path",
    "boq_document",
    "cited",
    "claim_lines",
    "cleanup_path",
    "contract_document",
    "delay_formula_inputs",
    "delay_values",
    "document_search_query",
    "document_text",
    "finance_inputs",
    "itp_text",
    "prepare_block_input",
    "semver",
    "validation_inputs",
]
