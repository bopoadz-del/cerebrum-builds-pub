"""gradebook_and_transcript -- the live weighted gradebook and its PDF.

Scope
  READS  the track's rubric weights, the component scores supplied for the
         learner, and the term; then drives the analytics, pdf, database and
         dashboard blocks.
  WRITES the weighted average, the live gradebook, a real PDF transcript
         under STORAGE_PATH/exports, and the extracted text of that PDF.
  NEVER  invents a missing component: a score the caller did not supply stays
         absent and the gradebook says so, instead of counting it as zero.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from app import domain, formulas, programme, track_schema
from app.block_inputs import BLOCK_DEFAULT_ACTIONS as _DEFAULT_ACTIONS
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "gradebook_and_transcript"
ENTITY = CAPABILITY_ID
BLOCK_IDS = ["analytics", "pdf", "database", "dashboard"]
BLOCK_DEFAULT_ACTIONS = {block: _DEFAULT_ACTIONS[block] for block in BLOCK_IDS}

COMPONENTS = ("memos", "defenses", "capstone")


def _export_dir() -> str:
    root = os.getenv("STORAGE_PATH") or "."
    path = os.path.join(root, "exports")
    os.makedirs(path, exist_ok=True)
    return path


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    try:
        track = track_schema.load_track(str(data.get("track_id") or "").strip() or track_schema.index()[0]["id"])
    except track_schema.TrackError as exc:
        return programme.refusal(CAPABILITY_ID, str(exc), field=exc.field, kind="schema_refused")
    except IndexError:
        return programme.refusal(CAPABILITY_ID, "no track files are shipped", field="track_id", kind="schema_refused")

    rubric = track.get("rubric") or {}
    weights = {name: domain.number((rubric.get("weights") or {}).get(name)) for name in COMPONENTS}
    supplied: Dict[str, Any] = {}
    for name in COMPONENTS:
        raw = data.get("%s_score" % name)
        if raw not in (None, ""):
            supplied[name] = domain.number(raw)
    missing = [name for name in COMPONENTS if name not in supplied]
    average = formulas.weighted_average(supplied, weights) if supplied else 0.0
    # prior_average is optional enrichment: a value that is not a number is
    # ignored rather than allowed to invalidate an otherwise complete
    # gradebook record.
    prior_raw = data.get("prior_average")
    try:
        prior = float(prior_raw) if prior_raw not in (None, "") else None
    except (TypeError, ValueError):
        prior = None
    growth = formulas.period_growth(prior, average) if prior is not None and supplied else None
    bands = dict(rubric.get("bands") or {})
    band = formulas.band_for(average, bands) if supplied else ""

    learner = domain.text(data.get("learner_email") or "guest@example.com")
    term = domain.integer(data.get("term"), 1) or 1
    reference = domain.text(data.get("reference") or "gradebook-%s-t%s" % (track.get("id"), term))
    grade_id = "%s@%s" % (domain.safe_slug(reference, "gradebook"), domain.text(track.get("file_version") or "v1"))

    grade_lines: List[str] = []
    contributions: Dict[str, Any] = {}
    for name in COMPONENTS:
        weight = domain.number(weights.get(name))
        if name in supplied:
            contribution = round(domain.number(supplied[name]) * weight / 100.0, 4)
            contributions[name] = contribution
            grade_lines.append(
                "%s [%s]: %.2f / 100 (weight %.0f%%, contributes %.4f) - %s"
                % (name, grade_id, domain.number(supplied[name]), weight, contribution, learner)
            )
        else:
            contributions[name] = None
            grade_lines.append("%s [%s]: not submitted (weight %.0f%%) - %s" % (name, grade_id, weight, learner))
    grade_lines.append("weighted_average [%s]: %.2f (%s) - %s" % (grade_id, average, band or "ungraded", learner))

    export_root = _export_dir()
    pdf_path = os.path.join(export_root, domain.safe_slug(reference, "transcript") + ".pdf")
    domain.write_pdf(
        pdf_path,
        "Transcript - %s" % domain.text(track.get("name")),
        [
            "Learner: %s" % learner,
            "Track: %s (version %s)" % (domain.text(track.get("id")), domain.text(track.get("file_version"))),
            "Term: %s" % term,
            "Grade id: %s" % grade_id,
            "",
            *grade_lines,
        ],
    )

    analytics_answer = execute(
        "analytics",
        {
            "metric": "weighted_average",
            "value": average,
            "period": "term-%s" % term,
            "tags": {"track": domain.text(track.get("id")), "term": term},
        },
        action="track_event",
    )
    pdf_answer = execute("pdf", {"file_path": pdf_path}, action="extract")
    database_answer = execute("database", {"table": ENTITY}, action="list_tables")
    dashboard_answer = execute(
        "dashboard",
        {
            "widgets": list(COMPONENTS) + ["weighted_average"],
            "refresh_interval": 60,
            "layout": {"name": "gradebook", "type": "grid", "columns": 2},
        },
        action="render",
    )

    answers = {
        "analytics": analytics_answer,
        "pdf": pdf_answer,
        "database": database_answer,
        "dashboard": dashboard_answer,
    }
    failure = domain.first_failure(CAPABILITY_ID, answers)
    if failure is not None:
        return failure

    extracted = ""
    for key in ("text", "content"):
        value = (pdf_answer or {}).get(key)
        if isinstance(value, str) and value.strip():
            extracted = value
            break
    if not extracted and isinstance((pdf_answer or {}).get("result"), dict):
        extracted = domain.text((pdf_answer.get("result") or {}).get("text"))

    record = {
        "reference": reference,
        "status": domain.text(data.get("status") or "open"),
        "learner_email": learner,
        "track_id": domain.text(track.get("id")),
        "track_version": domain.text(track.get("file_version")),
        "term": term,
        "memos_score": supplied.get("memos"),
        "defenses_score": supplied.get("defenses"),
        "capstone_score": supplied.get("capstone"),
        "weights": weights,
        "contributions": contributions,
        "missing_components": missing,
        "weighted_average": average,
        "band": band,
        "grade_id": grade_id,
        "grade_lines": grade_lines,
        "pdf_path": pdf_path,
        "pdf_characters": len(extracted),
        "pdf_text_has_average": ("%.2f" % average) in extracted if extracted else False,
        "term_over_term_growth": growth.get("value") if isinstance(growth, dict) and growth.get("ok") else None,
        "growth_definition": (
            (growth or {}).get("definition", {}).get("address") if isinstance(growth, dict) else None
        ),
        "authority": {"layer": 3, "label": "formula", "source": "writer:weighted_average_v1"},
    }
    return domain.ok(
        CAPABILITY_ID,
        record,
        answers,
        gradebook=grade_lines,
        weighted_average=average,
        missing_components=missing,
    )
