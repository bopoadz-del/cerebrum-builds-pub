"""Document intake and retrieval over the controlled document register.

The register holds one revision of one document. This module turns an uploaded
file into the searchable text a register entry stands for, and answers a
question over the text of the entries the caller's tenant already holds. It is
the retrieval behind the console's attach/ask surface -- no second database and
no invented corpus: the text kept here is read out of the file the caller
uploaded, and an answer that has no matching document is refused rather than
made up.

READS   an uploaded file (PDF, XLSX, CSV or text) and the tenant's register.
WRITES  the parsed text under STORAGE_PATH/workspace/intake/<tenant>/, beside
        the one persistence root -- never a record (the route persists).
NEVER   invents a document, an excerpt or a citation.
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app import store

#: Filing vocabulary the register declares; the intake maps a file to one of
#: them by what the file is, never by a particular customer's file name.
_REGISTER_TYPES = (
    "contract",
    "boq",
    "drawing",
    "itp",
    "certificate",
    "report",
    "claim",
    "correspondence",
)

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "and", "for", "that", "with", "what", "does", "this", "from",
    "about", "say", "said", "into", "are", "was", "were", "has", "have",
    "its", "their", "our", "you", "your", "document", "attached", "please",
    "which", "how", "many", "much", "when", "where", "why", "who",
}


def terms(text: str) -> List[str]:
    """The content words of a question or a document, in first-seen order."""
    out: List[str] = []
    for word in _WORD.findall(str(text or "").lower()):
        if len(word) > 2 and word not in _STOP and word not in out:
            out.append(word)
    return out


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))[:120] or "tenant"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:  # noqa: BLE001 - a fallback reader, never a fabricated answer
        pass
    # Some hand-written PDFs carry their text as a stream of literal strings.
    try:
        from pdfminer.high_level import extract_text as _pdfminer_text

        text = _pdfminer_text(io.BytesIO(data), password="").strip()
        if text:
            return text
    except Exception:  # noqa: BLE001
        pass
    chunks = re.findall(r"\(([^()\\]{2,})\)", _decode(data))
    return "\n".join(chunks)


def _xlsx_text(data: bytes) -> str:
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines: List[str] = []
        for sheet in workbook.worksheets:
            lines.append(f"# {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if value is None else str(value) for value in row]
                if any(cells):
                    lines.append("\t".join(cells))
        return "\n".join(lines)
    except Exception:  # noqa: BLE001
        return _decode(data)


def document_type_for(filename: str, text: str = "") -> str:
    """The register type this file is, from its suffix and its own content.

    It maps to the register's declared vocabulary; an unrecognised file is a
    report, which is what the register calls an unclassified controlled copy.
    """
    name = str(filename or "").lower()
    suffix = Path(name).suffix.lower()
    if "contract" in name or "agreement" in name:
        return "contract"
    if "boq" in name or "bill of quantities" in name or "bill_of_quantities" in name:
        return "boq"
    if "drawing" in name or suffix in (".dwg", ".dxf"):
        return "drawing"
    if "itp" in name or "inspection" in name:
        return "itp"
    if "certificate" in name or "cert" in name:
        return "certificate"
    if "claim" in name:
        return "claim"
    if "letter" in name or "correspondence" in name or "email" in name:
        return "correspondence"
    if suffix in (".xlsx", ".xlsm", ".xls", ".csv"):
        return "boq"
    if suffix in (".pdf", ".docx", ".doc", ".txt", ".md"):
        return "report"
    lowered = str(text or "").lower()
    for value in _REGISTER_TYPES:
        if value in lowered:
            return value
    return "report"


def parse_document(filename: str, data: bytes) -> Dict[str, Any]:
    """One uploaded file, parsed into the text its register entry stands for."""
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix == ".pdf":
        text = _pdf_text(data)
    elif suffix in (".xlsx", ".xlsm", ".xls"):
        text = _xlsx_text(data)
    else:
        text = _decode(data)
    text = text.strip()
    digest = checksum(data)
    return {
        "filename": str(filename or "upload"),
        "suffix": suffix or "",
        "checksum": digest,
        "document_type": document_type_for(filename, text),
        "text": text,
        "characters": len(text),
        "lines": len([line for line in text.splitlines() if line.strip()]),
        "reference": f"intake:{Path(str(filename or 'upload')).stem[:40]}:{digest[:12]}",
        "title": Path(str(filename or "upload")).stem or "upload",
    }


def intake_dir(tenant_id: str) -> Path:
    path = store.storage_root() / "workspace" / "intake" / _safe(tenant_id)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def keep_text(tenant_id: str, digest: str, text: str) -> str:
    """Persist the parsed text under the one storage root; return its name."""
    name = f"{_safe(digest)}.txt"
    path = intake_dir(tenant_id) / name
    try:
        path.write_text(text, encoding="utf-8")
    except OSError:
        return ""
    return name


def _register_entries(tenant_id: str) -> List[Dict[str, Any]]:
    try:
        return store.list_all("document_register", tenant_id=tenant_id)
    except Exception:  # noqa: BLE001 - an unopened schema has no entries
        return []


def _entry_text(tenant_id: str, entry: Dict[str, Any]) -> str:
    digest = str(entry.get("checksum") or "")
    if not digest:
        return ""
    path = intake_dir(tenant_id) / f"{_safe(digest)}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sentences(text: str) -> Iterable[str]:
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip()
            if len(sentence) >= 8:
                yield sentence


def search_entries(
    tenant_id: str,
    query: str = "",
    document_type: str = "",
) -> List[Dict[str, Any]]:
    """The tenant's register entries, filtered by a query and a type."""
    wanted = set(terms(query))
    rows: List[Dict[str, Any]] = []
    for entry in _register_entries(tenant_id):
        if document_type and str(entry.get("document_type") or "") != document_type:
            continue
        blob = " ".join(
            str(entry.get(key) or "")
            for key in ("reference", "title", "document_type", "revision", "source_document")
        )
        # A register search reaches the controlled copy's own text, not only
        # its metadata: the entry is the document the tenant holds.
        blob = blob + "\n" + _entry_text(tenant_id, entry)
        if wanted and not (wanted & set(terms(blob))):
            continue
        rows.append(entry)
    return rows


def answer(tenant_id: str, question: str, *, limit: int = 3) -> Dict[str, Any]:
    """Answer a question from the registered documents the tenant holds.

    Each candidate passage is scored by the question's own content words. A
    question with no matching passage is refused; nothing is answered from a
    document the tenant does not hold.
    """
    wanted = set(terms(question))
    if not wanted:
        return {"ok": False, "error": "the question names no content to look for", "citations": []}
    ranked: List[Tuple[int, str, str, str]] = []
    for entry in _register_entries(tenant_id):
        text = _entry_text(tenant_id, entry)
        if not text:
            continue
        citation = str(entry.get("source_document") or "")
        for sentence in _sentences(text):
            overlap = len(wanted & set(terms(sentence)))
            if overlap:
                ranked.append((overlap, sentence, citation, str(entry.get("title") or "")))
    if not ranked:
        return {
            "ok": False,
            "error": "no registered document answers that question; attach the document first",
            "citations": [],
        }
    ranked.sort(key=lambda row: (-row[0], row[1]))
    citations: List[Dict[str, Any]] = []
    for index, (score, sentence, citation, title) in enumerate(ranked[:limit], start=1):
        citations.append(
            {
                "index": index,
                "document": citation,
                "title": title,
                "excerpt": sentence[:500],
                "score": score,
            }
        )
    answer_text = " ".join(
        f"{row['excerpt']} [{row['index']}]" for row in citations
    )
    return {
        "ok": True,
        "question": question,
        "answer": answer_text,
        "citations": citations,
        "authority": "layer 2 documents",
    }


def source_of_record_answer(question: str, *, limit: int = 3) -> Dict[str, Any]:
    """Fall back to the contract excerpt the platform itself holds.

    The uploaded contract is the platform's source of record even before a
    caller attaches a copy; an answer cites it by its document id.
    """
    from app import contract_data

    wanted = set(terms(question))
    ranked: List[Tuple[int, str]] = []
    for sentence in _sentences(contract_data.contract_source_text()):
        overlap = len(wanted & set(terms(sentence)))
        if overlap:
            ranked.append((overlap, sentence))
    if not ranked:
        return {"ok": False, "error": "no clause in the source of record answers that question", "citations": []}
    ranked.sort(key=lambda row: (-row[0], row[1]))
    citations = [
        {
            "index": index,
            "document": contract_data.CONTRACT_DOCUMENT,
            "title": "contract excerpt",
            "excerpt": sentence[:500],
            "score": score,
        }
        for index, (score, sentence) in enumerate(ranked[:limit], start=1)
    ]
    return {
        "ok": True,
        "question": question,
        "answer": " ".join(f"{row['excerpt']} [{row['index']}]" for row in citations),
        "citations": citations,
        "authority": "layer 2 documents",
    }
