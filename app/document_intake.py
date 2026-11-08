"""Parsing and retrieval behind the controlled document register.

An uploaded file is turned into the text its register entry stands for, and a
question is answered only from text the platform holds: the tenant's
registered copies first, then the contract excerpt shipped as the platform's
source of record. Nothing here invents a document, an excerpt or a citation.

READS   an uploaded byte stream, the tenant's register entries, and the parsed
        copies kept under the one storage root.
WRITES  parsed text under STORAGE_PATH/workspace/intake/<tenant>/; never a
        register record (the HTTP route persists those).
NEVER   answers from a document the caller did not attach and the platform
        does not hold.
"""

from __future__ import annotations

import hashlib
import io
import re
import zlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app import store

#: Filing vocabulary the register declares. A file maps to one of these by
#: what it is (suffix and content), never by a particular customer's name.
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
    "which", "how", "many", "much", "when", "where", "why", "who", "under",
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


def _pdf_literal(raw: str) -> str:
    def _escape(match: "re.Match[str]") -> str:
        body = match.group(1)
        if body[:1] in ("n", "r", "t", "b", "f", "(", ")", "\\"):
            return {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(
                body[:1], body[:1]
            )
        if body[:1] in "01234567":
            try:
                return chr(int(body[:3], 8))
            except ValueError:
                return body[:1]
        return body

    return re.sub(r"\\([nrtbf()\\]|[0-7]{1,3})", _escape, raw)


def _pdf_streams(data: bytes) -> List[bytes]:
    """Every stream in the file, decompressed when it declares FlateDecode."""
    streams: List[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        body = match.group(1)
        header = data[max(0, match.start() - 400): match.start()]
        if b"FlateDecode" in header:
            try:
                body = zlib.decompress(body.rstrip(b"\r\n"))
            except zlib.error:
                continue
        streams.append(body)
    return streams


def _pdf_text(data: bytes) -> str:
    """Text drawn by a PDF, read from its literal strings.

    A PDF is a container of drawing operators; the text is the string
    arguments of the text operators (Tj, TJ, ' and "). Compressed streams are
    inflated first. A file whose text is an image or a custom font encoding
    yields nothing here and the intake refuses it rather than guessing.
    """
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        if text:
            return text
    except Exception:  # noqa: BLE001 - an optional reader, never a fabrication
        pass

    blobs = _pdf_streams(data) or [data]
    lines: List[str] = []
    pattern = re.compile(r"\(((?:\\.|[^\\()])*)\)\s*(?:Tj|TJ|'|\")", re.S)
    for blob in blobs:
        raw = blob.decode("latin-1", "replace")
        for match in pattern.finditer(raw):
            text = _pdf_literal(match.group(1)).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def _xlsx_text(data: bytes) -> str:
    """Cell text from an OOXML workbook, read without a spreadsheet engine."""
    try:
        from openpyxl import load_workbook  # type: ignore

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines: List[str] = []
        for sheet in workbook.worksheets:
            lines.append(f"# {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                cells = ["" if value is None else str(value) for value in row]
                if any(cells):
                    lines.append("\t".join(cells))
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 - fall through to the container reader
        pass
    try:
        import zipfile
        from xml.etree import ElementTree

        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        lines = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared: List[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in root.iter(namespace + "si"):
                    shared.append("".join(node.text or "" for node in item.iter(namespace + "t")))
            for name in sorted(n for n in archive.namelist() if n.startswith("xl/worksheets/sheet")):
                root = ElementTree.fromstring(archive.read(name))
                for row in root.iter(namespace + "row"):
                    cells: List[str] = []
                    for cell in row.iter(namespace + "c"):
                        kind = cell.get("t")
                        value = cell.find(namespace + "v")
                        if kind == "inlineStr":
                            inline = cell.find(namespace + "is")
                            text = "".join(
                                node.text or "" for node in inline.iter(namespace + "t")
                            ) if inline is not None else ""
                            cells.append(text)
                        elif value is not None and value.text is not None:
                            if kind == "s":
                                try:
                                    cells.append(shared[int(value.text)])
                                except (ValueError, IndexError):
                                    cells.append(value.text)
                            else:
                                cells.append(value.text)
                        else:
                            cells.append("")
                    if any(cells):
                        lines.append("\t".join(cells))
        return "\n".join(lines)
    except Exception:  # noqa: BLE001
        return ""


def document_type_for(filename: str, text: str = "") -> str:
    """The register type this file is, from its suffix and its own content."""
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
    """Persist parsed text under the one storage root; return its file name."""
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
        blob = blob + "\n" + _entry_text(tenant_id, entry)
        if wanted and not (wanted & set(terms(blob))):
            continue
        rows.append(entry)
    return rows


def _rank(
    wanted: set,
    sources: List[Tuple[str, str, str]],
    limit: int,
) -> List[Dict[str, Any]]:
    """Rank the sentences of the supplied documents by content-word overlap.

    ``sources`` is (citation, title, text). A sentence with no shared content
    word is not a candidate; a question that matches nothing gets no citation.
    """
    ranked: List[Tuple[int, str, str, str]] = []
    for citation, title, text in sources:
        for sentence in _sentences(text):
            overlap = len(wanted & set(terms(sentence)))
            if overlap:
                ranked.append((overlap, sentence, citation, title))
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
    return citations


def _answer_from_citations(question: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ok": True,
        "question": question,
        "answer": " ".join(f"{row['excerpt']} [{row['index']}]" for row in citations),
        "citations": citations,
        "authority": "layer 2 documents",
    }


def answer(tenant_id: str, question: str, *, limit: int = 3) -> Dict[str, Any]:
    """Answer from the registered copies the tenant holds."""
    wanted = set(terms(question))
    if not wanted:
        return {"ok": False, "error": "the question names no content to look for", "citations": []}
    sources: List[Tuple[str, str, str]] = []
    for entry in _register_entries(tenant_id):
        text = _entry_text(tenant_id, entry)
        if not text:
            continue
        sources.append(
            (
                str(entry.get("source_document") or ""),
                str(entry.get("title") or ""),
                text,
            )
        )
    citations = _rank(wanted, sources, limit)
    if not citations:
        return {
            "ok": False,
            "error": "no registered document answers that question; attach the document first",
            "citations": [],
        }
    return _answer_from_citations(question, citations)


def answer_from_documents(
    question: str,
    documents: List[Dict[str, Any]],
    *,
    limit: int = 3,
) -> Dict[str, Any]:
    """Answer from copies the caller attached in this session.

    This is the console's preview path before a copy is filed in the register.
    The text comes from the caller's own upload; the answer is labelled as a
    caller-supplied copy, not as a registered document.
    """
    wanted = set(terms(question))
    if not wanted:
        return {"ok": False, "error": "the question names no content to look for", "citations": []}
    sources: List[Tuple[str, str, str]] = []
    for document in documents or []:
        if not isinstance(document, dict):
            continue
        name = str(document.get("name") or document.get("title") or "attachment")
        text = str(document.get("text") or "")
        if text.strip():
            sources.append((f"document:{name}", name, text))
    citations = _rank(wanted, sources, limit)
    if not citations:
        return {
            "ok": False,
            "error": "the attached copy carries no passage that answers the question",
            "citations": [],
        }
    answer = _answer_from_citations(question, citations)
    answer["authority"] = "layer 2 documents (caller-supplied copy)"
    return answer


def source_of_record_answer(question: str, *, limit: int = 3) -> Dict[str, Any]:
    """Fall back to the contract excerpt the platform itself holds."""
    from app import contract_data

    wanted = set(terms(question))
    citations = _rank(
        wanted,
        [(contract_data.CONTRACT_DOCUMENT, "contract excerpt", contract_data.contract_source_text())],
        limit,
    )
    if not citations:
        return {
            "ok": False,
            "error": "no clause in the source of record answers that question",
            "citations": [],
        }
    return _answer_from_citations(question, citations)
