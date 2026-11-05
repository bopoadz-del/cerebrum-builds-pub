"""The gradebook: weighted average, hand-computed, and the transcript PDF."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_the_weighted_average_matches_a_hand_computation():
    from app.formulas import weighted_average

    # 60/20/20 of 86 / 82 / 90 = 51.6 + 16.4 + 18.0 = 86.0
    assert weighted_average(
        {"memos": 86, "defenses": 82, "capstone": 90},
        {"memos": 60, "defenses": 20, "capstone": 20},
    ) == 86.0


def test_a_missing_component_is_absent_not_zero():
    from app.formulas import weighted_average

    # memos 80 only: the mean of what exists is 80, not 80*0.6.
    assert weighted_average({"memos": 80}, {"memos": 60, "defenses": 20, "capstone": 20}) == 80.0


def test_the_route_computes_the_gradebook_and_writes_a_pdf(client, auth):
    resp = client.post(
        "/v1/gradebook_and_transcript",
        json={
            "reference": "gradebook-term-1",
            "status": "open",
            "track_id": "coo",
            "term": 1,
            "learner_email": "learner@example.com",
            "memos_score": 86,
            "defenses_score": 82,
            "capstone_score": 90,
        },
        headers=auth,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    record = body["record"]
    assert record["weighted_average"] == 86.0
    assert record["band"] == "B"
    assert record["missing_components"] == []

    PdfReader = pytest.importorskip("pypdf").PdfReader
    transcript = Path(record["pdf_path"])
    assert transcript.is_file() and transcript.stat().st_size > 0
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(transcript)).pages)
    for component in ("memos", "defenses", "capstone", "weighted_average"):
        assert component in text
    assert "86.00" in text
    assert record["grade_id"] in text


def test_a_partial_gradebook_says_which_component_is_missing(client, auth):
    resp = client.post(
        "/v1/gradebook_and_transcript",
        json={
            "reference": "gradebook-partial",
            "status": "open",
            "track_id": "coo",
            "term": 1,
            "learner_email": "learner@example.com",
            "memos_score": 74,
        },
        headers=auth,
    )
    record = resp.json()["record"]
    assert record["missing_components"] == ["defenses", "capstone"]
    assert record["weighted_average"] == 74.0
    assert record["contributions"]["defenses"] is None


def test_term_over_term_growth_uses_the_kernel_definition(client, auth):
    resp = client.post(
        "/v1/gradebook_and_transcript",
        json={
            "reference": "gradebook-growth",
            "status": "open",
            "track_id": "coo",
            "term": 2,
            "learner_email": "learner@example.com",
            "memos_score": 86,
            "defenses_score": 82,
            "capstone_score": 90,
            "prior_average": 80,
        },
        headers=auth,
    )
    record = resp.json()["record"]
    assert record["term_over_term_growth"] == 0.075
    assert record["growth_definition"] == "universal:period_over_period_growth_v1"


def test_a_score_above_one_hundred_is_refused(client, auth):
    resp = client.post(
        "/v1/gradebook_and_transcript",
        json={
            "reference": "gradebook-bad",
            "status": "open",
            "track_id": "coo",
            "memos_score": 140,
        },
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["rejected_field"] == "memos_score"
