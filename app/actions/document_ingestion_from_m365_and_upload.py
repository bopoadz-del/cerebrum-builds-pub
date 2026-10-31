"""Ingest plant documents from OneDrive/Outlook and direct uploads."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
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


def _write_plain_pdf(text: str, path: str) -> None:
    """Write a single-page PDF carrying ``text``.

    A text upload has no file to hand the PDF parser, so the same document
    is written as a one-page PDF and read back through the pdf block. That
    keeps one extraction path (and one provenance record) for uploads and
    for real files: the block is exercised on every ingest instead of only
    the ones that happen to arrive as PDFs. Only Latin-1 glyphs can be
    written by the base-14 font, so unsupported characters become '?'.
    """
    safe = text.encode("latin-1", "replace").decode("latin-1")
    safe = safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = [line for line in safe.splitlines() if line.strip()][:40] or ["empty"]
    stream = (
        "BT /F1 10 Tf 40 780 Td 14 TL "
        + " ".join("(%s) Tj T*" % line[:120] for line in lines)
        + " ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = "%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body))
        body += "%d 0 obj\n%s\nendobj\n" % (number, obj)
    xref = len(body)
    body += "xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        body += "%010d 00000 n \n" % offset
    body += "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    with open(path, "wb") as handle:
        handle.write(body.encode("latin-1"))


def _upload_root() -> Path:
    """Files an operator may point the parser at: uploads under the storage
    root only. A caller-supplied path is never read from the rest of the
    container filesystem (a second tenant's file, the database, /etc)."""
    configured = os.getenv("UPLOAD_ROOT")
    base = configured or os.path.join(
        os.getenv("STORAGE_PATH") or tempfile.gettempdir(), "uploads"
    )
    root = Path(base).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    name = str(record.get("document_name") or "")
    source = str(record.get("source") or "upload")
    text = str(record.get("content_text") or "")

    drive_item = str(record.get("drive_item_id") or "")
    drive = execute(
        "onedrive",
        {"operation": "status", "query": drive_item},
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

    if not text.strip():
        return {
            "ok": False,
            "error": "no_document_content",
            "capability_id": CAPABILITY_ID,
            "missing": ["content_text"],
            "drive_item_id": drive_item,
        }

    root = _upload_root()
    requested = str(record.get("file_path") or "")
    pdf_path = ""
    if requested:
        candidate = Path(requested).resolve()
        if candidate.is_file() and not candidate.is_relative_to(root):
            return {
                "ok": False,
                "error": "path_outside_upload_root",
                "capability_id": CAPABILITY_ID,
                "rejected_field": "file_path",
            }
        if candidate.is_file():
            pdf_path = str(candidate)
    temporary = ""
    if not pdf_path:
        # A text upload is handed to the same parser as a stored PDF.
        handle_file, temporary = tempfile.mkstemp(prefix="ingest-", suffix=".pdf")
        os.close(handle_file)
        _write_plain_pdf(text or name, temporary)
        pdf_path = temporary
    try:
        pdf_result = execute(
            "pdf",
            {"file_path": pdf_path},
            action=BLOCK_DEFAULT_ACTIONS.get("pdf"),
        )
        refused = block_failure("pdf", pdf_result)
        if refused:
            return refused
        extracted = str(pdf_result.get("text") or "")
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass

    if not text.strip():
        text = extracted

    saved = None
    if text.strip():
        saved = retrieval.ingest(
            text,
            source=source,
            document_name=name,
            document_type=str(record.get("document_type") or "bom"),
            tenant_id=current_tenant(),
            plant=str(record.get("plant") or ""),
        )

    return envelope(
        {
            "document_name": name,
            "source": source,
            "drive_authenticated": bool(drive.get("authenticated")),
            "m365_connections": int(m365.get("connections") or 0),
            "provenance_labels": len(provenance.get("labels") or []),
            "pdf_extracted": bool(str(pdf_result.get("text") or "").strip()),
            "pdf_pages": int(pdf_result.get("pages") or 0),
            "pdf_engine": pdf_result.get("engine"),
            "indexed": saved is not None,
            "document_id": (saved or {}).get("id"),
            "characters": len(text),
        },
        record,
    )
