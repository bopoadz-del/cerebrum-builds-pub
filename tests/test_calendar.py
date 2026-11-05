"""The generated calendar: 16 weeks x 6 sessions, in the learner's timezone."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app import schedule


@pytest.mark.parametrize(
    "start,timezone_name,expected_first",
    [
        (date(2026, 9, 3), "Asia/Dubai", "2026-09-03"),      # a Thursday
        (date(2026, 9, 7), "Australia/Brisbane", "2026-09-07"),  # a Monday
    ],
)
def test_ninety_six_sessions_from_thursday_and_monday_starts(start, timezone_name, expected_first):
    calendar = schedule.generate(start, timezone_name, 16)
    assert len(calendar) == 96
    assert calendar[0]["local_date"] == expected_first
    assert calendar[0]["kind"] == "framework"
    assert calendar[-1]["kind"] == "exam"
    assert {entry["week"] for entry in calendar} == set(range(1, 17))
    assert all(sum(1 for e in calendar if e["week"] == week) == 6 for week in range(1, 17))


def test_offset_three_is_a_rest_day():
    calendar = schedule.generate(date(2026, 9, 3), "Asia/Dubai", 16)
    assert 3 not in {entry["day_offset"] for entry in calendar}
    assert sorted({entry["day_offset"] for entry in calendar}) == [0, 1, 2, 4, 5, 6]


def test_the_template_durations_are_fixed():
    calendar = schedule.generate(date(2026, 9, 3), "UTC", 1)
    by_kind = {entry["kind"]: entry["minutes"] for entry in calendar}
    assert by_kind == {
        "framework": 90,
        "case_prep": 60,
        "case_class": 120,
        "lab": 90,
        "exam": 60,
    }
    assert [entry["minutes"] for entry in calendar] == [90, 60, 120, 90, 90, 60]


@pytest.mark.parametrize("timezone_name", ["Asia/Dubai", "Australia/Brisbane"])
def test_the_timezone_round_trips_on_every_session(timezone_name):
    calendar = schedule.generate(date(2026, 9, 3), timezone_name, 16)
    for entry in calendar:
        parsed = datetime.fromisoformat(entry["starts_at"])
        assert parsed.tzinfo is not None
        assert entry["timezone"] == timezone_name
        assert parsed.date().isoformat() == entry["local_date"]
        assert parsed.utcoffset() is not None


def test_an_unknown_timezone_is_refused():
    with pytest.raises(schedule.ScheduleError):
        schedule.generate(date(2026, 9, 3), "Mars/Olympus_Mons", 16)


def test_a_bad_start_date_is_refused():
    with pytest.raises(schedule.ScheduleError):
        schedule.generate("not-a-date", "UTC", 16)


def test_the_term_boundaries_follow_the_track_not_an_assumption():
    sessions = schedule.generate(date(2026, 9, 3), "UTC", 16)
    for entry in sessions:
        entry["term"] = ((entry["week"] - 1) // 4) + 1
    assert schedule.term_last_day(sessions, 1) == "2026-09-30"
    assert schedule.term_last_day(sessions, 4) == "2026-12-23"
