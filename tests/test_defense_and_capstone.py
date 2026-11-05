"""Defenses, re-sits, capstone acceptance and the graduation rule."""

from __future__ import annotations

from datetime import date

from app import schedule, track_schema


def _handler():
    from app.actions import defense_and_capstone

    return defense_and_capstone


def test_the_defense_is_scheduled_on_the_terms_last_day():
    track = track_schema.load_track("coo")
    term = track["terms"][0]
    numbers = [week["number"] for week in term["weeks"]]
    calendar = schedule.generate(date(2026, 9, 3), "Asia/Dubai", max(numbers))
    expected = [entry for entry in calendar if entry["week"] in numbers][-1]["local_date"]
    result = _handler().handle(
        {
            "reference": "def-1",
            "status": "open",
            "track_id": "coo",
            "term": 1,
            "kind": "defense",
            "start_date": "2026-09-03",
            "timezone": "Asia/Dubai",
            "verdict": "pass",
            "defense_passes": 3,
            "average": 84,
        }
    )
    assert result["ok"] is True
    assert result["record"]["scheduled_date"] == expected == "2026-09-30"
    assert result["record"]["defense_minutes"] == 45


def test_a_failed_defense_gets_a_resit_within_seven_days():
    result = _handler().handle(
        {
            "reference": "def-2",
            "status": "open",
            "track_id": "coo",
            "term": 1,
            "kind": "defense",
            "start_date": "2026-09-03",
            "verdict": "fail",
        }
    )
    record = result["record"]
    assert record["resit_date"] == "2026-10-07"
    assert record["resit_within_days"] == 7


def test_three_accepts_accept_the_capstone():
    result = _handler().handle(
        {
            "reference": "cap-1",
            "status": "open",
            "track_id": "coo",
            "term": 4,
            "kind": "capstone",
            "verdicts": ["accept", "accept", "accept"],
            "average": 85,
            "defense_passes": 4,
        }
    )
    assert result["record"]["capstone_acceptance"] == "accepted"
    assert result["record"]["graduation_ready"] is True


def test_two_accepts_and_a_revise_send_the_capstone_back_to_revision():
    result = _handler().handle(
        {
            "reference": "cap-2",
            "status": "open",
            "track_id": "coo",
            "term": 4,
            "kind": "capstone",
            "verdicts": ["accept", "accept", "revise"],
            "average": 85,
            "defense_passes": 4,
        }
    )
    assert result["record"]["capstone_acceptance"] == "revise"
    assert result["record"]["graduation_ready"] is False


def test_graduation_needs_the_average_the_four_passes_and_the_capstone():
    base = {
        "status": "open",
        "track_id": "coo",
        "term": 4,
        "kind": "capstone",
        "verdicts": ["accept", "accept", "accept"],
    }
    below = _handler().handle({"reference": "g-1", **base, "average": 79.9, "defense_passes": 4})
    assert below["record"]["graduation_ready"] is False

    three_passes = _handler().handle({"reference": "g-2", **base, "average": 90, "defense_passes": 3})
    assert three_passes["record"]["graduation_ready"] is False

    exactly = _handler().handle({"reference": "g-3", **base, "average": 80, "defense_passes": 4})
    assert exactly["record"]["graduation_ready"] is True


def test_two_reviewer_invites_are_composed_for_the_capstone():
    result = _handler().handle(
        {
            "reference": "cap-3",
            "status": "open",
            "track_id": "coo",
            "term": 2,
            "kind": "capstone",
            "reviewers": ["reviewer.one@example.com", "reviewer.two@example.com"],
            "verdicts": ["accept"],
        }
    )
    invites = result["record"]["capstone_invites"]
    assert len(invites) == 2
    assert "reviewer.one@example.com" in invites[0]
    assert result["record"]["email_status"] == "queued_not_sent_placeholder"


def test_an_unknown_term_is_refused_with_its_field():
    result = _handler().handle({"reference": "def-9", "status": "open", "track_id": "coo", "term": 9})
    assert result["ok"] is False
    assert result["rejected_field"] == "term"
