"""Constructed block inputs.

The caller of a capability supplies a domain record, never block-specific
keys.  This module turns that record into the inputs each bound block's own
contract reads -- including the prepared workflow children -- so no raw schema
sample ever reaches a block.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from openpyxl import Workbook

from app.dispatch import BLOCK_CONTRACTS

BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block: contract.get("action") for block, contract in BLOCK_CONTRACTS.items()
}


def default_block_action(block_id: str):
    return BLOCK_DEFAULT_ACTIONS.get(str(block_id))


def safe_stem(value: Any, fallback: str = "record") -> str:
    """A filename stem built from caller text: no separators, no traversal.

    ``reference`` is caller-supplied, so it is reduced to letters, digits,
    dash and underscore before it ever reaches a path (a dot can build "..");
    a value that reduces to nothing becomes the fallback, not the empty name.
    """
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-_")
    return text[:64] or fallback


def revision_ordinal(revision: Any) -> int:
    """The revision as a version component: A=1, B=2, numeric as itself.

    A revision string the contract does not number by letter is hashed to a
    stable ordinal rather than being silently treated as the first revision.
    """
    text = str(revision or "A").strip().upper()
    if len(text) == 1 and "A" <= text <= "Z":
        return ord(text) - ord("A") + 1
    if text.isdigit():
        return int(text)
    return 1 + (int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:6], 16) % 99)


def _iso_date(value: str) -> bool:
    """True when the value is an ISO date the schedule can start from."""
    from datetime import date

    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _root() -> Path:
    root = Path(os.environ.get("STORAGE_PATH") or ".")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _work_dir(capability_id: str) -> Path:
    path = _root() / "work" / str(capability_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


SOURCE_OF_RECORD = Path(__file__).resolve().parents[1] / "docs" / "source_of_record.json"
_CURRENCY_SHAPE = re.compile(r"[A-Z]{3}")


def source_declared_currency() -> str:
    """The currency the contract's own documents price in, read as data.

    ``docs/source_of_record.json`` records what the uploaded BOQ and contract
    excerpt declare; it carries no figure this platform invented. A deploy
    setting or the declared locale always wins over it (see
    ``configured_currency``), so an operator re-declaring the currency changes
    every money path without a code change.
    """
    try:
        body = json.loads(SOURCE_OF_RECORD.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return ""
    code = str(body.get("currency") or "").strip().upper()
    return code if _CURRENCY_SHAPE.fullmatch(code) else ""


def configured_currency() -> str:
    """The deployment's currency, in the order the operator sets it:
    the deploy environment, then the declared locale (both through
    ``app.money_settings``), then the contract's own declaration. Empty when
    none of them exists -- callers must not invent one."""
    try:
        from app.money_settings import currency

        code = str(currency() or "").strip().upper()
        if code:
            return code
    except Exception:
        pass
    return source_declared_currency()


def currency_of(record: Dict[str, Any]) -> str:
    declared = str((record or {}).get("currency") or "").strip()
    return declared.upper() if declared else configured_currency()


def digest(record: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(record or {}, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def summary(record: Dict[str, Any]) -> str:
    """A stable one-line description of the record, in field order."""
    parts: List[str] = []
    for key in sorted(record):
        value = record.get(key)
        if value in (None, "", []) or key.startswith("_"):
            continue
        if isinstance(value, (str, int, float, bool)):
            parts.append("%s=%s" % (key, value))
    return "; ".join(parts) or "record"


def write_artifact(capability_id: str, filename: str, content: Any) -> Path:
    path = _work_dir(capability_id) / filename
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(str(content), encoding="utf-8")
    return path


class _Finding:
    """A version finding the version_diff block reads by attribute."""

    def __init__(self, element_a: str, element_b: str, kind: str) -> None:
        self.element_a = element_a
        self.element_b = element_b
        self.kind = kind

    def as_dict(self) -> Dict[str, Any]:
        return {"element_a": self.element_a, "element_b": self.element_b, "kind": self.kind}

    def to_dict(self) -> Dict[str, Any]:
        return self.as_dict()


def _certificate_workbook(capability_id: str, record: Dict[str, Any], title: str) -> Path:
    """The document handed to the pdf block: a rendered, structured record.

    The block's own contract reads .xlsx/.csv/.pdf/.docx; a record the caller
    did not upload a PDF for is rendered as a worksheet so the extraction path
    is the block's own, not a stub.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Document"
    sheet.append([title])
    for key in sorted(record):
        if key.startswith("_"):
            continue
        sheet.append([str(key), str(record.get(key))])
    name = "%s_%s_%s.xlsx" % (
        safe_stem(record.get("reference")),
        digest(record)[:12],
        uuid.uuid4().hex[:10],
    )
    path = _work_dir(capability_id) / name
    workbook.save(path)
    return path


def _boq_rows(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """BOQ lines stated by the caller as ``item, description, unit, qty, rate``.

    A caller may supply the bill as text (CSV rows) or as ``boq_items`` on the
    record; either way the rows are parsed here, and an item the bill does not
    state yields no line rather than an invented one.
    """
    from app.boq import parse_rows

    raw = record.get("boq_items")
    if isinstance(raw, list):
        return parse_rows("\n".join(str(item) for item in raw))
    text = str(record.get("source_text") or "")
    return parse_rows(text) if text.strip() else []


def prepare_block_input(
    capability_id: str,
    block_id: str,
    record: Dict[str, Any],
    tenant_id: str = "",
) -> Dict[str, Any]:
    """The input one block reads for this capability's record."""
    record = dict(record or {})
    tenant = str(tenant_id or record.get("_tenant_id") or "local")
    reference = str(record.get("reference") or "record")
    text = str(record.get("source_text") or "").strip()
    line = summary(record)
    block = str(block_id)

    if block == "document_engine":
        return {
            "text": text or line,
            "brief": str(record.get("document_type") or capability_id),
            "extract_tables": False,
        }
    if block == "version":
        return {
            "block_id": reference,
            "version": "1.%d.0" % revision_ordinal(record.get("revision")),
            "changelog": [line],
        }
    if block == "version_diff":
        kind_pair = str(record.get("document_type") or "document")
        before = "clash" if str(record.get("supersedes") or "").strip() else "clear"
        return {
            "findings_v1": [_Finding(reference, kind_pair, before)],
            "findings_v2": [_Finding(reference, kind_pair, "clear")],
        }
    if block == "storage":
        filename = "%s_%s_%s.json" % (
            safe_stem(reference),
            digest(record)[:12],
            uuid.uuid4().hex[:10],
        )
        body = json.dumps(record, sort_keys=True, default=str)
        path = write_artifact(capability_id, filename, body)
        return {
            "action": "store",
            "content": body,
            "filename": filename,
            "file_path": str(path),
            "data_dir": str(_work_dir(capability_id) / "store"),
        }
    if block == "audit_chain":
        return {
            "action_execution_id": "ae_%s" % digest(record)[:20],
            "action_type": str(capability_id),
            "principal_id": str(record.get("principal_id") or "contract-administrator"),
            "project_id": reference,
            "payload": record,
            "result": {"reference": reference, "status": record.get("status") or "open"},
        }
    if block == "audit":
        return {
            "project_id": reference,
            "principal_id": "contract-administrator",
            "event": str(capability_id),
            "action_name": str(capability_id),
            "resource_type": str(capability_id),
            "resource_id": reference,
            "status": "ok",
            "details": {"summary": line},
        }
    if block == "boq_processor":
        # The block's declared readiness action: the parse engine answers
        # whether it can price a bill. Line pricing itself is formula-driven
        # (app/formulas) so the arithmetic is cited, not delegated blindly.
        payload: Dict[str, Any] = {}
        code = currency_of(record)
        if code:
            payload["currency"] = code
        return payload
    if block == "formula_executor":
        from app import formulas

        quantity = float(record.get("measured_quantity") or 0.0)
        rate = float(record.get("boq_rate") or 0.0)
        if capability_id == "delay_damages_tracking":
            expression = formulas.definition(formulas.LATE_FEE)["expression"]
            description = "delay damages under Clause 8.7"
            values = {
                "overdue_amount": float(record.get("accepted_contract_amount") or 0.0),
                "annual_rate": float(record.get("delay_damages_rate") or 0.0) * formulas.DAYS_IN_YEAR,
                "days_overdue": int(record.get("delay_days") or 0),
                "days_in_year": formulas.DAYS_IN_YEAR,
            }
        else:
            expression = formulas.definition(formulas.BOQ_LINE_AMOUNT)["expression"]
            description = "priced BOQ line for the certificate"
            values = {"measured_quantity": quantity, "boq_rate": rate}
        return {
            "formula_description": description,
            "custom_code": "result = " + str(expression),
            "input_values": values,
            "timeout_seconds": 5,
        }
    if block == "finance_reconciliation":
        certified = round(float(record.get("amount_certified") or 0.0), 2)
        measured = round(
            float(record.get("measured_quantity") or 0.0) * float(record.get("boq_rate") or 0.0), 2
        )
        return {
            "left_records": [{"key": reference, "amount": certified}],
            "right_records": [{"key": reference, "amount": measured}],
            "group_by": ["key"],
            "amount_field": "amount",
        }
    if block == "approval_rules":
        approver = str(record.get("approver") or "contract-administrator")
        return {
            "action": "ingest",
            "project_id": reference,
            "source_doc": text or line,
            "extracted": [
                {
                    "rule_id": "certificate_approval",
                    "text": "interim payment certificate approved by %s" % approver,
                }
            ],
        }
    if block == "pdf":
        title = {
            "progress_claims": "Interim Payment Certificate",
        }.get(str(capability_id), "Controlled Record")
        path = _certificate_workbook(capability_id, record, title)
        return {"file_path": str(path), "extract_tables": False}
    if block == "cpm_engine":
        days = max(1, int(record.get("delay_days") or 1))
        payload = {
            "activities": [
                {"id": "A1", "name": "works", "duration": days, "predecessors": []},
                {
                    "id": "A2",
                    "name": "taking-over",
                    "duration": 1,
                    "predecessors": [{"predecessor_id": "A1", "type": "FS", "lag": 0}],
                },
            ]
        }
        start = str(record.get("commencement_date") or "").strip()
        if _iso_date(start):
            payload["project_start"] = start
        return payload
    if block == "finance_planning":
        code = currency_of(record)
        payload = {
            "tenant_id": tenant,
            "amount": "%.2f" % float(record.get("damages_assessed") or 0.0),
            "period": str(record.get("reference") or "period"),
        }
        if code:
            payload["currency_code"] = code
        return payload
    if block == "evidence_chain":
        return {
            "action": "record",
            "tenant_id": tenant,
            "action_type": "qa_inspection",
            "principal_id": str(record.get("inspector") or "qa-engineer"),
            "payload": record,
            "result": {"outcome": str(record.get("outcome") or "pass")},
        }
    if block == "validation":
        item = {
            "id": reference,
            "type": str(record.get("inspection_type") or "qa_inspection"),
            "quantity": float(record.get("measured_quantity") or 1.0),
        }
        if record.get("boq_item"):
            item["description"] = str(record.get("boq_item"))
        return {
            "item": item,
            "context": {"capability_id": str(capability_id), "reference": reference},
        }
    if block == "workflow":
        return {
            "pipeline_id": "%s-%s" % (capability_id, reference),
            "trigger": "manual",
            "steps": workflow_steps(capability_id, record, tenant),
        }
    if block == "knowledge":
        return {
            "query": text or line,
            "project_id": tenant,
            "top_k": 5,
        }
    if block == "regulatory_chunker":
        return {
            "text": text or line,
            "doc": str(record.get("clause_id") or reference),
            "section": str(record.get("clause_id") or "clause"),
        }
    if block == "evidence_or_refuse":
        evidence_ref = str(record.get("evidence_ref") or "").strip()
        claim = str(record.get("clause_id") or reference)
        return {
            "action": "judge",
            "claims": [
                {
                    "id": claim,
                    "evidence": [evidence_ref] if evidence_ref else [],
                }
            ],
        }
    if block == "governance_gate":
        return {
            "action": "create_request",
            "tenant_id": tenant,
            "action_type": "contract_clause_adopt",
            "target_id": str(record.get("clause_id") or reference),
            "requester_id": "contract-administrator",
        }
    if block == "finance_canonical_model":
        code = currency_of(record)
        if not code:
            raise ValueError("no currency declared for the finance ledger")
        return {
            "operation": "validate_record",
            "record_type": "project_cost",
            "record": {
                "record_id": reference,
                "project_id": str(record.get("project") or "harbourline"),
                "entity_id": tenant,
                "period": str(record.get("period") or "2026-09"),
                "currency": code,
                "amount": "%.2f" % float(record.get("amount_held") or 0.0),
            },
        }
    if block == "transaction_state_machine":
        return {
            "operation": "allowed",
            "entity_id": str(record.get("reference") or "record"),
            "vertical": "transaction",
        }
    if block == "dashboard":
        # The operator surfaces are configured through the block's own
        # ui_schema inputs; the action stays the block's declared default.
        return {
            "user_id": "contract-administrator",
            "action": "render",
            "default_layout": "grid",
            "refresh_interval": 30,
            "max_widgets": 20,
            "theme": "light",
        }
    if block == "analytics":
        metric = "certified_total" if "certified_total" in record else "delay_days"
        return {
            "metric": metric,
            "value": float(record.get(metric) or 0.0),
            "tags": {"reference": reference, "capability": str(capability_id)},
        }
    if block == "portfolio_rollup":
        return {
            "properties": [
                {
                    "id": reference,
                    "value": float(record.get("earned_value") or record.get("certified_total") or 0.0),
                    "status": str(record.get("status") or "active"),
                },
                {
                    "id": "retention",
                    "value": float(record.get("retention_total") or 0.0),
                    "status": "held",
                },
            ]
        }
    return dict(record)


def event_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "reference": str(record.get("reference") or "record"),
        "status": str(record.get("status") or "open"),
    }
    for key in ("amount_certified", "delay_days", "outcome", "amount_held"):
        if record.get(key) not in (None, ""):
            payload[key] = record[key]
    return payload


def workflow_step(
    capability_id: str,
    block_id: str,
    action: Optional[str],
    payload: Dict[str, Any],
    step_id: str,
) -> Dict[str, Any]:
    """One prepared child: block, action and a constructed input."""
    step: Dict[str, Any] = {
        "id": step_id,
        "block": str(block_id),
        "action": action,
        "input": dict(payload or {}),
    }
    if action is not None:
        step["input"].setdefault("action", action)
    return step


def workflow_steps(
    capability_id: str,
    record: Dict[str, Any],
    tenant_id: str = "",
) -> List[Dict[str, Any]]:
    """The prepared pipeline for a capability's workflow binding.

    Every child is built from the record through the same builders the direct
    calls use, so a workflow step is never a raw schema sample.
    """
    steps: List[Dict[str, Any]] = []
    if capability_id == "qa_itp_records":
        steps.append(
            workflow_step(
                capability_id,
                "validation",
                BLOCK_DEFAULT_ACTIONS.get("validation"),
                prepare_block_input(capability_id, "validation", record, tenant_id),
                "step_0",
            )
        )
        steps.append(
            workflow_step(
                capability_id,
                "evidence_chain",
                BLOCK_DEFAULT_ACTIONS.get("evidence_chain"),
                prepare_block_input(capability_id, "evidence_chain", record, tenant_id),
                "step_1",
            )
        )
    return steps
