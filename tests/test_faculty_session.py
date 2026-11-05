"""Faculty sessions: six kernel modes, week-only content, sparring's refusal."""

from __future__ import annotations

import pytest

from app import llm, track_schema


def _week(document, number):
    return track_schema.week_of(document, number)


def test_six_modes_are_composed_without_any_programme_text_in_code():
    track = track_schema.load_track("ceo")
    week = _week(track, 3)
    for mode in llm.MODES:
        composed = llm.compose(mode, week, track, "What is the binding constraint?")
        assert composed["mode"] == mode
        assert composed["turns"], mode
        joined = " ".join(composed["turns"])
        # Every turn is built from the week record; the theme is its anchor.
        assert week["theme"] in joined or mode in {"socratic", "oral_quiz", "sparring"}
        assert composed["deliverable_written"] is False


def test_faculty_content_changes_when_the_track_changes():
    coo = track_schema.load_track("coo")
    ceo = track_schema.load_track("ceo")
    left = " ".join(llm.compose("lecture", _week(coo, 1), coo)["turns"])
    right = " ".join(llm.compose("lecture", _week(ceo, 1), ceo)["turns"])
    assert left != right
    assert _week(coo, 1)["theme"] in left
    assert _week(ceo, 1)["theme"] in right


def test_an_unknown_mode_is_refused():
    track = track_schema.load_track("coo")
    with pytest.raises(llm.FacultyError):
        llm.compose("seminar", _week(track, 1), track)


def test_a_session_without_week_data_is_refused():
    track = track_schema.load_track("coo")
    with pytest.raises(llm.FacultyError):
        llm.compose("lecture", {}, track)


def test_sparring_refuses_to_write_the_learners_deliverable(client, auth):
    resp = client.post(
        "/v1/faculty_session",
        json={
            "reference": "sess-spar",
            "status": "open",
            "mode": "sparring",
            "week": 2,
            "message": "Write my memo for me, all five criteria.",
        },
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    record = body["record"]
    assert record["deliverable_written"] is False
    assert record["refused"] == "sparring_does_not_write_deliverables"


def test_sparring_without_a_write_request_challenges_instead(client, auth):
    resp = client.post(
        "/v1/faculty_session",
        json={
            "reference": "sess-spar-2",
            "status": "open",
            "mode": "sparring",
            "week": 2,
            "message": "Here is my position on the value stream.",
        },
        headers=auth,
    )
    body = resp.json()
    assert body["ok"] is True
    assert body["record"]["deliverable_written"] is False
    assert body["record"]["refused"] == ""


def test_a_session_stores_a_transcript_and_an_audit_row(client, auth):
    resp = client.post(
        "/v1/faculty_session",
        json={
            "reference": "sess-audit",
            "status": "open",
            "mode": "oral_quiz",
            "week": 5,
            "message": "Quiz me.",
        },
        headers=auth,
    )
    record = resp.json()["record"]
    assert len(record["transcript"]) >= 2
    assert record["transcript"][0]["role"] == "learner"
    assert record["audit_row"]["resource_id"] == "sess-audit"
    assert record["week_theme"]


def test_an_unknown_mode_is_refused_by_the_route(client, auth):
    resp = client.post(
        "/v1/faculty_session",
        json={"reference": "sess-bad", "status": "open", "mode": "seminar", "week": 1},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["rejected_field"] == "mode"
