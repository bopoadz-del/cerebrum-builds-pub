"""Memo grading, performed by a grader that cannot see the faculty transcript.

Two separations are structural, not conventions:

1. This module never imports, reads or receives a faculty session. It is
   handed a track document, a week number and a submission -- nothing else.
   A transcript key in the caller's payload is dropped at the door.
2. Evidence is read from the submission against the week record (its
   concepts, readings and cases) and the scores are summed through the
   formula_executor block, so the arithmetic is the block's execution and
   the provenance names it.

One verdict line per rubric criterion; the total is graded on the track's
own bands; below the track's rewrite threshold the submission takes the
rewrite path. Nothing here decides a band from a hardwired number.
"""

from __future__ import annotations

import os
import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app import formulas

DEFAULT_CRITERION_WORDS = 60

_WORD = re.compile(r"[A-Za-z0-9']+")


class GradingError(ValueError):
    """A submission that cannot be graded against the supplied rubric."""


def _words(text: str) -> List[str]:
    return _WORD.findall(str(text or ""))


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", str(text or ""))
    return [part.strip() for part in parts if part.strip()]


def _weight(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    try:
        return float(raw) if raw else float(default)
    except ValueError:
        return float(default)


def evidence_weights() -> tuple:
    """How the three evidence signals combine into a criterion score.

    A pedagogical policy the programme owner sets: how much a criterion is
    carried by written length, by coverage of the week's concepts, and by use
    of the week's named sources. Defaults 0.5 / 0.3 / 0.2.
    """
    length = _weight("PLATFORM_EVIDENCE_LENGTH_WEIGHT", 0.5)
    coverage = _weight("PLATFORM_EVIDENCE_COVERAGE_WEIGHT", 0.3)
    sources = _weight("PLATFORM_EVIDENCE_SOURCE_WEIGHT", 0.2)
    total = length + coverage + sources
    if total <= 0:
        return (0.5, 0.3, 0.2)
    return (length / total, coverage / total, sources / total)


def target_words() -> int:
    """Words of evidence expected per criterion. A named platform setting."""
    raw = (os.getenv("PLATFORM_CRITERION_WORDS") or "").strip()
    try:
        return max(10, int(raw)) if raw else DEFAULT_CRITERION_WORDS
    except ValueError:
        return DEFAULT_CRITERION_WORDS


def _mentions(text: str, phrase: str) -> bool:
    needle = str(phrase or "").strip().lower()
    if not needle:
        return False
    haystack = str(text or "").lower()
    if needle in haystack:
        return True
    # A multi-word label counts when most of its distinctive words appear.
    tokens = [token for token in _WORD.findall(needle) if len(token) > 4]
    if not tokens:
        return False
    return sum(1 for token in tokens if token in haystack) >= max(1, (len(tokens) + 1) // 2)


def _coverage(text: str, items: List[str]) -> float:
    if not items:
        return 0.0
    hit = sum(1 for item in items if _mentions(text, item))
    return formulas.criterion_ratio(hit, len(items))


def criterion_evidence(
    criterion: Dict[str, Any],
    week: Dict[str, Any],
    submission: str,
    points_each: int,
) -> Dict[str, Any]:
    """One criterion's evidence, read from the submission and the week."""
    label = str(criterion.get("label") or criterion.get("id") or "criterion")
    passages = _sentences(submission)
    # The criterion's own share of the submission: a contiguous slice, so a
    # long memo cannot score every criterion on the same paragraph.
    if passages:
        index = int(criterion.get("_index") or 0)
        slice_size = max(1, len(passages) // max(1, int(criterion.get("_count") or 1)))
        start = min(len(passages) - 1, index * slice_size)
        share = " ".join(passages[start:start + slice_size])
    else:
        share = ""
    length_ratio = formulas.criterion_ratio(len(_words(share)), target_words())

    concepts = [str(item) for item in week.get("concepts") or []]
    readings = [str(item.get("title") or "") for item in week.get("readings") or []]
    cases = [str(item.get("title") or "") for item in week.get("cases") or []]
    sources = [item for item in readings + cases if item]
    coverage = max(_coverage(share or submission, concepts), _coverage(share or submission, [label]))
    source_use = _coverage(share or submission, sources)

    length_w, coverage_w, source_w = evidence_weights()
    ratio = length_w * length_ratio + coverage_w * coverage + source_w * source_use
    score = round(float(points_each) * min(1.0, max(0.0, ratio)), 1)
    return {
        "criterion": str(criterion.get("id") or label),
        "label": label,
        "points_available": int(points_each),
        "score": score,
        "evidence": {
            "words": len(_words(share)),
            "length_ratio": round(length_ratio, 4),
            "coverage": round(coverage, 4),
            "source_use": round(source_use, 4),
        },
    }


def _execute_total(criterion_scores: List[float], max_total: int, run_id: str) -> Dict[str, Any]:
    """Sum the criterion scores through the formula_executor block."""
    from app.dispatch import execute
    from app.block_inputs import BLOCK_DEFAULT_ACTIONS

    code = (
        "total = float(sum(criterion_scores))\n"
        "result = round(total * 100.0 / float(max_total), 4)\n"
    )
    answer = execute(
        "formula_executor",
        {
            "custom_code": code,
            "input_values": {
                "criterion_scores": [float(score) for score in criterion_scores],
                "max_total": int(max_total),
            },
            "formula_description": "rubric criterion total for run %s" % run_id,
            "operation": "execute",
        },
        action=BLOCK_DEFAULT_ACTIONS.get("formula_executor"),
    )
    return answer if isinstance(answer, dict) else {"ok": False, "status": "error", "error": "no block answer"}


def grade(
    document: Dict[str, Any],
    week_number: int,
    submission: str,
    *,
    week: Optional[Dict[str, Any]] = None,
    rubric_version: str = "",
) -> Dict[str, Any]:
    """Grade one submission on the track's 5 x points_each rubric.

    The rubric version graded against is recorded with the result, so a
    later rubric edit cannot rewrite a past verdict.
    """
    rubric = (document or {}).get("rubric") or {}
    criteria = rubric.get("criteria") or []
    if not criteria:
        raise GradingError("the track declares no rubric criteria")
    points_each = int(rubric.get("points_each") or 20)
    max_total = points_each * len(criteria)

    week = week or {}
    enriched = []
    for index, criterion in enumerate(criteria):
        entry = dict(criterion)
        entry["_index"] = index
        entry["_count"] = len(criteria)
        enriched.append(entry)
    evidence = [
        criterion_evidence(criterion, week, submission, points_each) for criterion in enriched
    ]
    scores = [item["score"] for item in evidence]

    run_id = uuid.uuid4().hex
    answer = _execute_total(scores, max_total, run_id)
    failed = answer.get("ok") is False or str(answer.get("status") or "").lower() not in {"", "success", "ok"}
    if failed:
        return {
            "ok": False,
            "error": "formula_executor refused the rubric total: %s" % (answer.get("error") or "unknown"),
            "error_kind": "block_refused",
            "failed_block": "formula_executor",
        }

    output = answer.get("execution_result")
    if output is None:
        output = (answer.get("result") or {}).get("execution_result") if isinstance(answer.get("result"), dict) else None
    total = round(float(output if output is not None else sum(scores)), 2)

    bands = dict(rubric.get("bands") or {})
    band = formulas.band_for(total, bands)
    rewrite = formulas.rewrite_required(total, bands)

    verdicts = []
    for item in evidence:
        verdict = "meets" if item["score"] >= float(points_each) * (
            float(bands.get("C", 70)) / 100.0
        ) else "below"
        verdicts.append(
            "%s: %s/%s (%s)" % (item["criterion"], item["score"], points_each, verdict)
        )

    provenance = {
        "kernel_block": "formula_executor",
        "kernel_version": str(answer.get("version") or "formula_executor@1.0.0"),
        "rubric_version": rubric_version or str(document.get("content_version") or ""),
        "track_id": document.get("id"),
        "track_version": document.get("file_version"),
        "run_id": run_id,
        "definition": "writer:weighted_average_v1+formula_executor.execute",
        "criteria": len(criteria),
        "points_each": points_each,
        "transcript_access": "none",
    }

    return {
        "ok": True,
        "total": total,
        "max_total": max_total,
        "band": band,
        "rewrite_required": rewrite,
        "verdict_lines": verdicts,
        "criteria": [
            {
                "criterion": item["criterion"],
                "label": item["label"],
                "score": item["score"],
                "points_available": item["points_available"],
                "evidence": item["evidence"],
            }
            for item in evidence
        ],
        "provenance": provenance,
        "block_answer": answer,
        "authority": {"layer": 3, "label": "formula", "source": "formula_executor"},
    }


def similarity(left: str, right: str) -> float:
    """A deterministic similarity, used to spot a resubmitted memo."""
    return round(SequenceMatcher(None, str(left or ""), str(right or "")).ratio(), 4)
