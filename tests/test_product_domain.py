"""The domain decisions: what the platform decides, not just what it stores.

A handler that stores a row where the brief asked for a decision is unfinished
work. These tests pin the decisions: track admission and its version diff,
memo bands and the re-sit, the 60/20/20 average, the six kernel modes and
sparring's refusal, the case-reveal rule, and the 16x6 schedule.
"""

from __future__ import annotations

import datetime as dt

import pytest

from app import formulas, llm
from app.actions import _support, ai_faculty_sessions, enrolment_and_scheduling, library_surfaces, track_management
from app.actions import gradebook_and_transcript, memo_grading
from app.models import MODELS
from app.validation import sample_for_model, validate_payload
from tests import product_testkit as kit


def test_track_schema_refuses_an_invalid_document_with_its_field_path():
    bad = "schema: track.v1\ntrack_key: coo\ntitle: ''\nweeks: 0\n"
    out = track_management._validate(
        {"schema": "track.v1", "track_key": "coo", "title": "", "weeks": 0, "session_template": [], "weeks_detail": []}
    )
    assert out, "an empty track document must not validate"
    assert any("title" in error or "weeks" in error for error in out)
    assert bad


def test_track_document_synthesised_from_a_seed_has_a_full_term():
    document = track_management._seed_document("coo")
    assert document["weeks"] == 16
    assert len(document["weeks_detail"]) == 16
    assert len(document["session_template"]) == 6
    assert track_management._validate(document) == []


def test_week_diff_names_the_weeks_that_changed():
    before = track_management._seed_document("ceo")
    after = dict(before)
    after["weeks_detail"] = [dict(item) for item in before["weeks_detail"]]
    after["weeks_detail"][2]["theme"] = "A rewritten week"
    after["weeks_detail"].pop()
    diff = track_management._week_diff(before, after)
    assert {entry["week"] for entry in diff} == {3, 16}
    assert any(entry["change"] == "changed" and entry["week"] == 3 for entry in diff)
    assert any(entry["change"] == "removed" and entry["week"] == 16 for entry in diff)


def test_memo_grader_scores_five_criteria_and_bands_the_total():
    strong = (
        "This memo argues that the constraint is the packing line because throughput "
        "collapses at 82% utilisation. Per the plant data, 41% of late orders start there. "
        "However, the risk is that a second shift raises defect rates; the counter-case is a "
        "temporary cell. I recommend we commit to the cell for twelve weeks, owned by operations, "
        "reviewed on 2026-12-01."
    )
    grade = llm.grade_memo(strong, learner_id="l-1")
    assert len(grade["criteria"]) == 5
    assert all(0 <= item["score"] <= 20 for item in grade["criteria"])
    assert grade["total"] == sum(item["score"] for item in grade["criteria"])
    assert grade["band"] in {"pass", "merit", "distinction", "resit"}
    assert len(grade["verdict_lines"]) == 5
    assert grade["faculty_transcript_visible"] is False
    assert grade["resit_required"] is (grade["total"] < 70)


def test_memo_grader_puts_a_thin_memo_in_the_resit_band():
    grade = llm.grade_memo("Things are hard.", rubric_version="rubric.v1")
    assert grade["total"] < 70
    assert grade["band"] == "resit"
    assert grade["resit_required"] is True


def test_weighted_average_is_sixty_twenty_twenty():
    row = formulas.weighted_average(90, 80, 70)
    assert row["value"] == pytest.approx(84.0)
    assert formulas.weighted_average(0, 0, 0)["value"] == 0.0


def test_faculty_modes_map_from_the_session_kind():
    assert llm.mode_for("framework") == "lecture"
    assert llm.mode_for("case_prep") == "brief"
    assert llm.mode_for("case_class") == "socratic"
    assert llm.mode_for("lab") == "sparring"
    assert llm.mode_for("exam") == "examiner"
    assert llm.mode_for("framework", "oral_quiz") == "oral_quiz"
    assert llm.mode_for("unknown-kind") == "lecture"


def test_sparring_refuses_to_draft_the_deliverable():
    spar = llm.faculty_reply("sparring", "Draft my memo for me", session_kind="lab", week=5)
    assert spar["refuses_draft"] is True
    assert "will not draft" in spar["answer"]
    lecture = llm.faculty_reply("lecture", "Explain the constraint", session_kind="framework", week=1)
    assert lecture["refuses_draft"] is False


def test_case_outcome_is_withheld_outside_the_case_class(client, monkeypatch):
    kit.stub_blocks(monkeypatch)
    before = library_surfaces.handle(
        {"reference": "lib-1", "track_key": "coo", "week": 3, "session_kind": "case_prep"}
    )
    assert before["result"]["case"]["revealed"] is False
    assert before["result"]["case"]["outcome"] is None
    during = library_surfaces.handle(
        {"reference": "lib-2", "track_key": "coo", "week": 3, "session_kind": "case_class"}
    )
    assert during["result"]["case"]["revealed"] is True


def test_schedule_expands_sixteen_weeks_of_six_sessions():
    zone = enrolment_and_scheduling._timezone("Europe/London")
    start = dt.date(2026, 9, 7)
    sessions = enrolment_and_scheduling._schedule(start, zone)
    assert len(sessions) == 96
    assert {item["kind"] for item in sessions} == {"framework", "case_prep", "case_class", "lab", "exam"}
    assert sessions[0]["starts_at"].startswith("2026-09-07")
    assert sessions[-1]["week"] == 16


def test_memo_handler_refuses_when_a_block_refuses(monkeypatch):
    def refusing(block_id, payload=None, action=None, params=None, **kw):
        return {"ok": False, "status": "error", "block": block_id, "error": "gate: forced"}

    kit.stub_blocks(monkeypatch)
    monkeypatch.setattr(_support, "execute", refusing, raising=False)
    out = memo_grading.handle({"reference": "m-1", "memo_text": "a memo"})
    assert out["ok"] is False
    assert out["error_kind"] == "block_failure"


def test_gradebook_handler_marks_a_below_floor_learner(monkeypatch):
    kit.stub_blocks(monkeypatch)
    out = gradebook_and_transcript.handle(
        {"reference": "g-1", "learner_id": "l-1", "memos_score": 70, "defenses_score": 60, "capstone_score": 60}
    )
    assert out["ok"] is True
    assert out["result"]["weighted_average"] == pytest.approx(66.0)
    assert out["result"]["passed"] is False
    assert out["result"]["band"] == "below_floor"
    assert out["result"]["transcript"]["bytes"] > 0


def test_faculty_handler_refuses_success_over_a_failed_block(monkeypatch):
    def refusing(block_id, payload=None, action=None, params=None, **kw):
        return {"ok": False, "status": "error", "block": block_id, "error": "gate: forced"}

    kit.stub_blocks(monkeypatch)
    monkeypatch.setattr(_support, "execute", refusing, raising=False)
    out = ai_faculty_sessions.handle({"reference": "f-1", "session_kind": "lab", "week": 2})
    assert out["ok"] is False


def test_missing_required_field_is_named_by_the_validator():
    _, violations = validate_payload(MODELS["memo_grading"], {"status": "open"})
    assert violations and violations[0]["field"] == "reference"
    assert violations[0]["reason"] == "missing_required"
    assert sample_for_model(MODELS["memo_grading"])["reference"] == "sample"
