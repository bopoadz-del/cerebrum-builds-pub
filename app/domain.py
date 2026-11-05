"""Shared domain plumbing for the capability handlers.

Pure functions: number coercion, block-answer handling, and the two export
formats the platform actually produces (PDF and XLSX) with the standard
library only -- no network, no hidden renderer.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape

from app.authority import authority_label
from app.dispatch import failed


def text(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if result == result else float(default)


def integer(value: Any, default: int = 0) -> int:
    return int(round(number(value, default)))


def flag(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def record_reference(payload: Dict[str, Any], prefix: str) -> str:
    reference = text(payload.get("reference") or payload.get("id") or "").strip()
    if reference:
        return reference
    return "%s-%s" % (prefix, datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f"))


def safe_slug(value: Any, fallback: str = "record") -> str:
    """A filename-safe stem for an export.

    A reference is customer-supplied text. It is sanitised before it ever
    reaches a path: only letters, digits, dot, dash and underscore survive,
    leading dots are stripped, and an empty result becomes ``fallback``.
    This is the guard that keeps ``reference="../../etc/passwd"`` inside
    the export directory.
    """
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip(".-_")
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned[:120]


def block_answers(entries: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for block_id, answer in entries.items():
        if isinstance(answer, dict):
            summary[block_id] = {
                "ok": not failed(answer),
                "status": answer.get("status") or ("error" if answer.get("ok") is False else "ok"),
            }
        else:
            summary[block_id] = {"ok": True, "status": "ok"}
    return summary


def first_failure(capability_id: str, entries: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for block_id, answer in entries.items():
        if failed(answer):
            return {
                "ok": False,
                "capability_id": capability_id,
                "error": "%s refused: %s"
                % (block_id, text((answer or {}).get("error") if isinstance(answer, dict) else answer, "block failure")),
                "failed_block": block_id,
                "error_kind": (answer or {}).get("error_kind") if isinstance(answer, dict) else None,
                "authority": authority_label(1),
                "blocks": block_answers(entries),
            }
    return None


def ok(capability_id: str, record: Dict[str, Any], entries: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ok": True,
        "capability_id": capability_id,
        "record": record,
        "authority": authority_label(1),
        "blocks": block_answers(entries),
    }
    body.update(extra)
    return body


# --------------------------------------------------------------------------
# PDF: a small, valid PDF 1.4 with real text (Helvetica, WinAnsi).
# --------------------------------------------------------------------------
def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(line: str, width: int = 92) -> List[str]:
    words = str(line).split()
    if not words:
        return [""]
    out: List[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > width and current:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def build_pdf(title: str, lines: Iterable[str]) -> bytes:
    content_lines: List[str] = [title, ""]
    for line in lines:
        content_lines.extend(_wrap(str(line)))
    pages: List[List[str]] = []
    per_page = 48
    for index in range(0, max(1, len(content_lines)), per_page):
        pages.append(content_lines[index : index + per_page])

    objects: List[bytes] = []
    page_ids: List[int] = []
    # 1 catalog, 2 pages, 3 font, then page + content pairs
    next_id = 4
    for _page in pages:
        page_ids.append(next_id)
        next_id += 2

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join("%d 0 R" % pid for pid in page_ids)
    objects.append(("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))).encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    for page_id, body in zip(page_ids, pages):
        stream_parts = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for line in body:
            stream_parts.append("(%s) Tj" % _pdf_escape(line))
            stream_parts.append("T*")
        stream_parts.append("ET")
        stream = "\n".join(stream_parts).encode("latin-1", "replace")
        page_obj = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (page_id + 1)
        ).encode()
        content_obj = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        objects.append(page_obj)
        objects.append(content_obj)

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: List[int] = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(("%d 0 obj\n" % index).encode())
        out.write(obj)
        out.write(b"\nendobj\n")
    xref_at = out.tell()
    out.write(("xref\n0 %d\n" % (len(objects) + 1)).encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.write(("%010d 00000 n \n" % offset).encode())
    out.write(
        ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)).encode()
    )
    return out.getvalue()


def write_pdf(path: str, title: str, lines: Iterable[str]) -> str:
    data = build_pdf(title, lines)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


# --------------------------------------------------------------------------
# XLSX: one sheet, inline strings, real OOXML package.
# --------------------------------------------------------------------------
def _cell_column(index: int) -> str:
    name = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        name = chr(65 + remainder) + name
    return name


def build_xlsx(rows: Iterable[Iterable[Any]], sheet_name: str = "Scorecard") -> bytes:
    matrix = [list(row) for row in rows]
    sheet_rows: List[str] = []
    for r_index, row in enumerate(matrix, start=1):
        cells: List[str] = []
        for c_index, value in enumerate(row):
            ref = "%s%d" % (_cell_column(c_index), r_index)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append('<c r="%s"><v>%s</v></c>' % (ref, value))
            else:
                cells.append(
                    '<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                    % (ref, escape(str(value if value is not None else "")))
                )
        sheet_rows.append('<row r="%d">%s</row>' % (r_index, "".join(cells)))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>%s</sheetData></worksheet>" % "".join(sheet_rows)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>' % escape(sheet_name)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def write_xlsx(path: str, rows: Iterable[Iterable[Any]], sheet_name: str = "Scorecard") -> str:
    with open(path, "wb") as handle:
        handle.write(build_xlsx(rows, sheet_name))
    return path
