"""P1 capture adapter. Factory CLONER emission.

Local OCR when tesseract is on PATH; otherwise scripted extraction from
provided text. No cloud LLM. No Ollama. No outbound HTTP.

Replaces the Store shim in the product workspace so a delivered platform
cannot inherit cloud-LLM defaults while block.json says network:false.
The Factory vendor-mirror Store-shim snapshot is unchanged. Blocks was not written.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

POSTURE = "P1"


def _local_ocr(path: Path) -> str:
    exe = shutil.which("tesseract")
    if not exe or not path.is_file():
        return ""
    try:
        proc = subprocess.run(
            [exe, str(path), "stdout", "-l", "eng"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()


def _scripted_structure(raw: str) -> Dict[str, Any]:
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)
    urls = re.findall(r"https?://\S+", raw)
    numbers = re.findall(r"\b\d+(?:\.\d+)?\b", raw)
    summary = raw[:240] + ("…" if len(raw) > 240 else "")
    return {
        "entities": {
            "emails": emails,
            "urls": urls,
            "numbers": numbers[:20],
        },
        "tags": ["p1", "scripted"],
        "summary": summary,
        "clean_text": " ".join(raw.split()),
    }


def _extract_text(data: Dict[str, Any]) -> tuple[str, str]:
    for key in ("raw_text", "text", "content", "body"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), "scripted"
    for key in ("path", "file", "image", "input"):
        value = data.get(key)
        if isinstance(value, (str, Path)) and Path(value).is_file():
            ocr = _local_ocr(Path(value))
            if ocr:
                return ocr, "tesseract"
            return "", "tesseract_unavailable"
    return "", "scripted"


def run(**kwargs: Any) -> Dict[str, Any]:
    data = kwargs.get("input", kwargs)
    if not isinstance(data, dict):
        data = {"input": data}
    raw, engine = _extract_text(data)
    structured = _scripted_structure(raw)
    digest = hashlib.sha256((raw or "empty").encode("utf-8")).hexdigest()[:16]
    return {
        "posture": POSTURE,
        "capture_id": digest,
        "raw_text": raw,
        "ocr_engine": engine,
        "llm_provider": "none",
        **structured,
    }
