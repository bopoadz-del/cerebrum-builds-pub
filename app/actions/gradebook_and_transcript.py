"""gradebook_and_transcript -- the live weighted average and the transcript.

Weights are the programme's own: memos 60, defenses 20, capstone 20. The
average is recomputed on every read from the components (never cached as a
number someone typed), the mastery floor decides pass/fail, and a transcript
PDF carrying every grade is issued and hashed so the copy a learner holds can
be checked against the one the registrar issued.

READS   the three component scores and the operator's mastery floor.
WRITES  the weighted average, the transcript artifact under STORAGE_PATH and
        the analytics/dashboard rows via the blocks.
NEVER   issues a transcript over a failed analytics or pdf block, or rounds a
        score into a pass it did not earn.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from typing import Any, Dict, List

from app import authority, formulas
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "gradebook_and_transcript"
ENTITY = "gradebook_and_transcript"
BLOCK_IDS = ["analytics", "dashboard", "pdf", "audit"]

WEIGHTS = {"memos": 60, "defenses": 20, "capstone": 20}


def _floor() -> float:
    raw = (os.environ.get("PLATFORM_MASTERY_FLOOR") or "").strip()
    try:
        return float(raw) if raw else 80.0
    except ValueError:
        return 80.0


def _pdf(lines: List[str]) -> bytes:
    """A one-page PDF carrying the transcript lines (no external library)."""
    def _escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    parts: List[str] = ["BT", "/F1 12 Tf", "14 TL", "56 780 Td"]
    for line in lines[:48]:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    stream = "\n".join(parts).encode("latin-1", "replace")

    objects: List[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    learner = _support.text_of(record, "learner_id") or "learner"
    scores = {
        "memos": _support.number_of(record, "memos_score"),
        "defenses": _support.number_of(record, "defenses_score"),
        "capstone": _support.number_of(record, "capstone_score"),
    }
    average_row = formulas.weighted_average(scores["memos"], scores["defenses"], scores["capstone"])
    average = float(average_row["value"])
    floor = _floor()
    passed = average >= floor
    band = formulas.band(average, pass_floor=floor) if passed else "below_floor"

    lines = [
        "Cerebrum Executive Programs -- Academic Transcript",
        f"Learner: {learner}",
        f"Reference: {reference}",
        "",
        f"Memos (weight {WEIGHTS['memos']}%): {scores['memos']:.1f}",
        f"Term defenses (weight {WEIGHTS['defenses']}%): {scores['defenses']:.1f}",
        f"Capstone (weight {WEIGHTS['capstone']}%): {scores['capstone']:.1f}",
        f"Weighted average: {average:.2f}",
        f"Mastery floor: {floor:.1f} -- {'PASS' if passed else 'BELOW FLOOR'}",
        f"Band: {band}",
        "",
        "Issued by Cerebrum Executive Programs. Grades are computed from the",
        "recorded components; a transcript is issued only over a stored gradebook.",
    ]
    pdf_bytes = _pdf(lines)
    workspace = _support.workspace_dir(CAPABILITY_ID)
    # Concurrent submissions of the same reference must not write the same
    # file at the same time: a reader would parse a half-written PDF. A unique
    # name per issue plus an atomic replace makes every issue complete.
    transcript = workspace / (
        f"transcript_{_support.digest(reference)[:16]}_{uuid.uuid4().hex[:8]}.pdf"
    )
    partial = transcript.with_suffix(".part")
    partial.write_bytes(pdf_bytes)
    os.replace(partial, transcript)
    digest = hashlib.sha256(pdf_bytes).hexdigest()

    inputs: Dict[str, Dict[str, Any]] = {
        "analytics": {
            "metrics": {
                "weighted_average": average,
                "memos": scores["memos"],
                "defenses": scores["defenses"],
                "capstone": scores["capstone"],
                "mastery_floor": floor,
                "pass": passed,
            },
            "series": [
                {"stage": "memos", "value": scores["memos"], "weight": WEIGHTS["memos"]},
                {"stage": "defenses", "value": scores["defenses"], "weight": WEIGHTS["defenses"]},
                {"stage": "capstone", "value": scores["capstone"], "weight": WEIGHTS["capstone"]},
            ],
            "topic": f"gradebook.{reference}",
        },
        "dashboard": {
            "action": "render",
            "widgets": [
                {"kind": "score", "label": "Weighted average", "value": average},
                {"kind": "status", "label": "Standing", "value": "pass" if passed else "below floor"},
            ],
            "layout": {"columns": 2, "refresh_interval": 60},
            "reference": reference,
        },
        "pdf": {
            "path": str(transcript),
            "file_path": str(transcript),
            "title": "Academic Transcript",
            "lines": lines,
            "pages": 1,
            "bytes": len(pdf_bytes),
        },
        "audit": {
            "action": "log",
            "actor": CAPABILITY_ID,
            "entity": ENTITY,
            "reference": reference,
            "detail": {"average": average, "transcript_sha256": digest, "pass": passed},
        },
    }

    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    result = {
        "reference": reference,
        "learner_id": learner,
        "components": scores,
        "weights": WEIGHTS,
        "weighted_average": round(average, 2),
        "average_expression": average_row["expression"],
        "mastery_floor": floor,
        "passed": passed,
        "band": band,
        "transcript": {
            "path": str(transcript),
            "sha256": digest,
            "bytes": len(pdf_bytes),
            "pages": 1,
            "grades": lines[4:7],
        },
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(3),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
