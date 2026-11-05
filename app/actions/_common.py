"""Shared plumbing for the capability handlers.

Nothing here decides domain questions: it turns a block's refusal into the
capability's refusal, so a handler can never answer ok:true over a block that
failed (F1).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app import dispatch

AUTHORED_BY = "codewhale exec"


class BlockRefused(RuntimeError):
    def __init__(self, block_id: str, message: str, answer: Optional[Dict[str, Any]] = None):
        super().__init__(f"{block_id}: {message}")
        self.block_id = block_id
        self.message = message
        self.answer = answer or {}


_UNSET = object()


def call(block_id: str, payload: Optional[Dict[str, Any]] = None, action: Any = _UNSET) -> Dict[str, Any]:
    """Run a locked block; raise when it refuses; return its result body.

    Blocks answer in two shapes: the flat result the adapter returns, or the
    full envelope (``block_id``/``status``/``result``) when the adapter
    returns the envelope. Both are normalised here to the result body.
    """
    body = dict(payload or {})
    if action is _UNSET:
        answer = dispatch.execute(block_id, body)
    else:
        answer = dispatch.execute(block_id, body, action=action)
    failure = dispatch.failure_of(answer)
    if failure is not None:
        raise BlockRefused(block_id, failure, answer)
    if "block_id" in answer and isinstance(answer.get("result"), dict):
        return dict(answer["result"])
    return answer


def refusal(message: str, *, field: Optional[str] = None, status: int = 422) -> Dict[str, Any]:
    body: Dict[str, Any] = {"ok": False, "error": str(message), "status": "refused"}
    if field:
        body["rejected_field"] = field
    return body


def envelope(record: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "record": record, "result": result, "id": record.get("id")}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_date(value: Any) -> Optional[_dt.date]:
    if value in (None, ""):
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def digest(text: Any) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(value: Any, fallback: str = "record") -> str:
    """A caller-supplied label made safe for a filename: no separators, no
    traversal, bounded length."""
    text = _SAFE.sub("-", str(value or "")).strip("-.")
    return (text or fallback)[:80]


def currency_code() -> str:
    """The currency this deployment prices in, read from app.money_settings.

    An undeclared currency is not a refusal: the platform still computes and
    records the figures, and the operator sets PLATFORM_CURRENCY to have them
    labelled.
    """
    from app import money_settings

    try:
        return money_settings.currency()
    except Exception:  # noqa: BLE001 - an unset setting is not a domain refusal
        return ""


def scratch_path(stem: str, suffix: str) -> Path:
    """A unique scratch file under the platform's work directory.

    Unique per call, so two requests -- from any tenant -- never share a path
    and cannot read each other's rendered document.
    """
    import uuid

    name = f"{safe_name(stem)}-{uuid.uuid4().hex[:16]}{suffix}"
    return work_dir() / name


def work_dir(prefix: str = "harbourline-") -> Path:
    root = Path(os.environ.get("STORAGE_PATH") or tempfile.gettempdir())
    path = root / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_file(name: str, content: str, prefix: str = "harbourline-") -> Path:
    path = work_dir(prefix=prefix) / name
    path.write_text(content, encoding="utf-8")
    return path


def render_pdf(path: Path, lines) -> Path:
    """A one-page PDF carrying the certificate's text.

    Hand-built content stream: no rendering dependency, and the pdf block
    then proves the document reads back.
    """
    text = " ".join(str(line).replace("(", "[").replace(")", "]") for line in lines)
    # A PDF content stream is a byte string: encode to latin-1 with
    # replacement so any unicode a caller typed renders as "?" instead of
    # raising UnicodeEncodeError mid-certificate.
    text = text.encode("latin-1", "replace").decode("latin-1")
    stream = f"BT /F1 11 Tf 56 780 Td ({text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj {body} endobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n"
    out += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    )
    path.write_bytes(out.encode("latin-1", "replace"))
    return path


def jsonish(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    return json.loads(json.dumps(value, default=str))
