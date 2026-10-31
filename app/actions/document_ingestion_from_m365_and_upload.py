"""Ingest plant documents from OneDrive/Outlook and direct uploads."""

from __future__ import annotations

from typing import Any, Dict

from app import retrieval
from app.actions._common import block_failure, envelope
from app.dispatch import execute
from app.tenancy import current_tenant

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "document_ingestion_from_m365_and_upload"
ENTITY = "document_ingestion_from_m365_and_upload"
BLOCK_IDS = ["onedrive", "microsoft_365", "ingestion_provenance", "pdf"]
BLOCK_DEFAULT_ACTIONS = {
    "onedrive": None,
    "microsoft_365": None,
    "ingestion_provenance": None,
    "pdf": None,
}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "env", "scope": "process"},
    {"kind": "config", "scope": "runtime"},
]
WRITES = [
    {"kind": "caller", "scope": "output"},
    {"kind": "database", "scope": "tenant_corpus"},
]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    name = str(record.get("document_name") or "")
    source = str(record.get("source") or "upload")
    text = str(record.get("content_text") or "")
    file_path = str(record.get("file_path") or "")

    drive = execute(
        "onedrive",
        {"operation": "status"},
        action=BLOCK_DEFAULT_ACTIONS.get("onedrive"),
    )
    refused = block_failure("onedrive", drive)
    if refused:
        return refused

    m365 = execute(
        "microsoft_365",
        {"action": "status"},
        action=BLOCK_DEFAULT_ACTIONS.get("microsoft_365"),
    )
    refused = block_failure("microsoft_365", m365)
    if refused:
        return refused

    provenance = execute(
        "ingestion_provenance",
        {"action": "list_labels"},
        action=BLOCK_DEFAULT_ACTIONS.get("ingestion_provenance"),
    )
    refused = block_failure("ingestion_provenance", provenance)
    if refused:
        return refused

    pdf_result: Dict[str, Any] = {"extracted": False}
    if file_path:
        pdf_result = execute(
            "pdf",
            {"file_path": file_path},
            action=BLOCK_DEFAULT_ACTIONS.get("pdf"),
        )
        refused = block_failure("pdf", pdf_result)
        if refused:
            return refused
        extracted = pdf_result.get("text") or ""
        text = text or extracted

    saved = None
    if text.strip():
        saved = retrieval.ingest(
            text,
            source=source,
            document_name=name,
            document_type=str(record.get("document_type") or "bom"),
            tenant_id=current_tenant(),
        )

    return envelope(
        {
            "document_name": name,
            "source": source,
            "drive_authenticated": bool(drive.get("authenticated")),
            "m365_connections": int(m365.get("connections") or 0),
            "provenance_labels": len(provenance.get("labels") or []),
            "pdf_extracted": bool(pdf_result.get("extracted")),
            "indexed": saved is not None,
            "document_id": (saved or {}).get("id"),
            "characters": len(text),
        },
        record,
    )
