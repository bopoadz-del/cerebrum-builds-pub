"""memo_grading -- a separate grader with no access to the faculty transcript.

Scope
  READS  the track's rubric and the week record, the submitted memo, and the
         tenant's provenance document; then drives the formula_executor,
         validation, evidence_chain and ingestion_provenance blocks.
  WRITES one verdict line per rubric criterion, the total, its band, the
         rewrite decision, and provenance naming the kernel block, its
         version, the rubric version and the run id.
  NEVER  reads, imports or receives a faculty session. A transcript in the
         payload is dropped at the door and the grader records that it had
         none -- the separation is what makes the verdict independent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app import domain, grading, programme, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "memo_grading"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["formula_executor", "validation", "evidence_chain", "ingestion_provenance"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}

ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = ROOT / "docs" / "provenance" / "provenance.json"
_CONFIDENTIAL_KEYS = ("transcript", "faculty_transcript", "session_transcript")


def _provenance_document() -> Dict[str, Any]:
    try:
        return json.loads(PROVENANCE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    # The separation is enforced here: a grader never sees a session.
    for key in _CONFIDENTIAL_KEYS:
        data.pop(key, None)

    try:
        track = track_schema.load_track(str(data.get("track_id") or "").strip() or track_schema.index()[0]["id"])
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")
    except IndexError:
        return programme.refusal(CAPABILITY_ID, "no track files are shipped", field="track_id", kind="schema_refused")

    week_number = domain.integer(data.get("week"), 1) or 1
    try:
        week = track_schema.week_of(track, week_number)
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")

    submission = domain.text(data.get("submission"))
    rubric_version = domain.text(data.get("rubric_version") or track.get("content_version"))
    try:
        result = grading.grade(track, week_number, submission, week=week, rubric_version=rubric_version)
    except grading.GradingError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field="submission", kind="schema_refused")

    if result.get("ok") is False:
        return programme.refusal(
            CAPABILITY_ID,
            str(result.get("error") or "the grader refused the submission"),
            field="submission",
            kind=str(result.get("error_kind") or "block_refused"),
        )

    reference = domain.text(data.get("reference") or "memo-%s-w%s" % (track.get("id"), week_number))
    tenant_id = programme.tenant(data)
    principal = programme.principal(data)

    validation_answer = execute(
        "validation",
        {
            "item": {
                "id": reference,
                "type": "memo",
                "value": float(result["total"]),
                "quantity": float(len(grading._words(submission))),
            },
            "context": {"points_each": result["provenance"]["points_each"]},
        },
        action="validate_pipeline",
    )
    evidence_answer = execute(
        "evidence_chain",
        {
            "tenant_id": tenant_id,
            "action_type": "memo_grading",
            "principal_id": principal,
            "payload": {"reference": reference, "criteria": len(result["criteria"])},
            "result": {"total": result["total"], "band": result["band"], "run_id": result["provenance"]["run_id"]},
        },
        action="record",
    )
    source = _provenance_document()
    provenance_answer = execute(
        "ingestion_provenance",
        {
            "product_id": str(source.get("product_id") or "product"),
            "blueprint_id": str(source.get("blueprint_id") or ""),
            "factory_commit": str(source.get("factory_commit") or ""),
            "blocks_commit": str(source.get("blocks_commit") or ""),
            "inputs_hash": str(source.get("inputs_hash") or ""),
            "plan": source.get("plan") or {},
        },
        action="build",
    )

    answers = {
        "formula_executor": result.get("block_answer") or {"status": "success", "ok": True},
        "validation": validation_answer,
        "evidence_chain": evidence_answer,
        "ingestion_provenance": provenance_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    record = {
        "reference": reference,
        "status": domain.text(data.get("status") or "open"),
        "learner_email": domain.text(data.get("learner_email") or "guest@example.com"),
        "track_id": domain.text(track.get("id")),
        "track_version": domain.text(track.get("file_version")),
        "week": week_number,
        "submission": submission,
        "submission_words": len(grading._words(submission)),
        "rubric_version": rubric_version,
        "total": result["total"],
        "max_total": result["max_total"],
        "band": result["band"],
        "rewrite_required": bool(result["rewrite_required"]),
        "rewrite_path": "rewrite" if result["rewrite_required"] else "graded",
        "verdict_lines": result["verdict_lines"],
        "criteria": result["criteria"],
        "provenance": result["provenance"],
        "transcript_access": "none",
        "authority": result["authority"],
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        verdict_lines=result["verdict_lines"],
        provenance=result["provenance"],
        rewrite_required=bool(result["rewrite_required"]),
    )
