"""memo_grading -- the separate AI grader, scored against the rubric.

The grader never sees the faculty transcript: it reads the submitted memo and
the rubric version only, which is what makes its judgement independent of the
conversation the learner had while writing. Five criteria are scored 0-20, the
total is computed by a formula (never typed in), the band follows the
operator's floors, and every criterion gets one verdict line. Under the pass
floor the memo triggers a re-sit rather than a pass with a warning.

READS   the submitted memo, the rubric version, the operator's thresholds.
WRITES  the grade, its provenance (kernel block version, rubric version, run
        id) and one audit row; the ROUTE persists the record.
NEVER   reads the faculty transcript, scores a memo it was not given, or
        reports ok around a block that refused.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from app import authority, block_inputs, llm
from app.actions import _support
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "memo_grading"
ENTITY = "memo_grading"
BLOCK_IDS = ["formula_executor", "evidence_chain", "evidence_verifier", "answer_quality_scorer", "audit_chain", "validation"]

KERNEL_BLOCK_VERSION = "cerebrum-blocks@store.pin-4e832448"


def _threshold(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    tenant = block_inputs.tenant_scope(record)
    learner = _support.text_of(record, "learner_id")
    memo = _support.text_of(record, "memo_text")
    rubric_version = _support.text_of(record, "rubric_version") or llm.RUBRIC_VERSION

    pass_floor = _threshold("PLATFORM_MEMO_PASS_FLOOR", 70.0)
    merit_floor = _threshold("PLATFORM_MEMO_MERIT_FLOOR", 80.0)
    distinction_floor = _threshold("PLATFORM_MEMO_DISTINCTION_FLOOR", 90.0)

    grade = llm.grade_memo(
        memo,
        rubric_version=rubric_version,
        learner_id=learner,
        pass_floor=pass_floor,
        merit_floor=merit_floor,
        distinction_floor=distinction_floor,
    )

    claims: List[Dict[str, Any]] = [
        {"text": line["verdict"], "layer": 3, "criterion": line["criterion"]}
        for line in grade["verdict_lines"]
    ]
    inputs: Dict[str, Dict[str, Any]] = {
        "formula_executor": {
            "formula_id": "product:memo_criterion_total_v1",
            "expression": grade["total_expression"],
            "inputs": {item["criterion"]: item["score"] for item in grade["criteria"]},
            "values": {item["criterion"]: item["score"] for item in grade["criteria"]},
            "topic": f"memo.{reference}.graded",
        },
        "evidence_chain": {
            "tenant_id": tenant,
            "action_type": "memo_grading",
            "principal_id": reference,
            "claims": claims,
            "sources": [
                {"id": f"rubric:{rubric_version}", "layer": 3, "excerpt": "rubric.v1 criteria"},
                {"id": f"memo:{grade['memo_sha256'][:16]}", "layer": 2, "excerpt": memo[:400]},
            ],
            "reference": reference,
        },
        "evidence_verifier": {
            "id": f"{reference}:{grade['run_id']}",
            "content": {"memo_sha256": grade["memo_sha256"], "total": grade["total"]},
            "evidence": [{"claim": c["text"], "source": f"rubric:{rubric_version}"} for c in claims],
            "memo_text": memo,
            "strict": True,
        },
        "answer_quality_scorer": {
            "answer": memo,
            "rubric": {
                "version": rubric_version,
                "criteria": grade["rubric_notes"],
                "max_score": 20,
            },
            "criteria_scores": {item["criterion"]: item["score"] for item in grade["criteria"]},
        },
        "audit_chain": {
            "action_execution_id": f"{reference}:memo:{grade['run_id']}",
            "action_type": "memo_graded",
            "principal_id": reference,
            "tenant_id": tenant,
            "entity": ENTITY,
            "reference": reference,
            "actor": CAPABILITY_ID,
            "detail": {
                "run_id": grade["run_id"],
                "rubric_version": rubric_version,
                "total": grade["total"],
                "band": grade["band"],
            },
        },
        "validation": {
            "value": grade["total"],
            "claim": "memo total within 0-100",
            "ranges": {"total": [0, 100]},
            "strict": True,
        },
    }

    answers, refusal = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs=inputs)
    if refusal:
        return refuse(f"block refused: {refusal}", "block_failure", blocks=answers)

    result = {
        "reference": reference,
        "learner_id": learner,
        "rubric_version": grade["rubric_version"],
        "criteria": grade["criteria"],
        "verdict_lines": grade["verdict_lines"],
        "total": grade["total"],
        "total_expression": grade["total_expression"],
        "band": grade["band"],
        "pass_floor": pass_floor,
        "merit_floor": merit_floor,
        "distinction_floor": distinction_floor,
        "resit_required": grade["resit_required"],
        "next_step": "resit" if grade["resit_required"] else "recorded",
        "memo_sha256": grade["memo_sha256"],
        "word_count": grade["word_count"],
        "provenance": {
            "run_id": grade["run_id"],
            "grader": grade["grader"],
            "kernel_block_version": KERNEL_BLOCK_VERSION,
            "rubric_version": grade["rubric_version"],
            "formula_id": "product:memo_criterion_total_v1",
        },
        "faculty_transcript_visible": False,
        "blocks": {block_id: answers.get(block_id, {}).get("status") for block_id in BLOCK_IDS},
        "authority": authority.label(3),
    }
    return ok(CAPABILITY_ID, result, record={"reference": reference})
