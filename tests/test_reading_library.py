"""The reading and case library: sources published, outcomes withheld."""

from __future__ import annotations

from datetime import date, timedelta

from app import schedule, track_schema


def _library():
    from app.actions import reading_and_case_library

    return reading_and_case_library


def _coo_week(week: int):
    track = track_schema.load_track("coo")
    return track, track_schema.week_of(track, week)


def test_a_week_publishes_its_readings_and_cases_with_sources():
    _track, week = _coo_week(1)
    result = _library().handle(
        {
            "reference": "lib-1",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "start_date": date.today().isoformat(),
            "timezone": "UTC",
        }
    )
    assert result["ok"] is True
    readings = result["record"]["readings"]
    cases = result["record"]["cases"]
    assert len(readings) == len(week["readings"])
    assert all(item["source"] for item in readings)
    assert all(item["source"] for item in cases)


def test_the_outcome_is_withheld_before_the_case_class_session():
    future = (date.today() + timedelta(days=30)).isoformat()
    result = _library().handle(
        {
            "reference": "lib-2",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "start_date": future,
            "timezone": "UTC",
            "session_offset": 1,
        }
    )
    record = result["record"]
    assert record["outcome_released"] is False
    assert all(case["outcome"] == "" for case in record["cases"])
    assert all(case["outcome_withheld"] is True for case in record["cases"])


def test_the_outcome_opens_once_the_case_class_session_has_run():
    started = (date.today() - timedelta(days=7)).isoformat()
    result = _library().handle(
        {
            "reference": "lib-3",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "start_date": started,
            "timezone": "UTC",
            "session_offset": 0,
        }
    )
    record = result["record"]
    assert record["outcome_released"] is True
    assert record["cases"][0]["outcome"]
    assert record["case_class_opens_on"]


def test_a_learner_cannot_unlock_an_outcome_early_with_an_offset():
    future = (date.today() + timedelta(days=30)).isoformat()
    result = _library().handle(
        {
            "reference": "lib-6",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "start_date": future,
            "timezone": "UTC",
            "session_offset": 5,
            "_roles": ["Learner"],
        }
    )
    record = result["record"]
    assert record["outcome_released"] is False
    assert all(case["outcome"] == "" for case in record["cases"])


def test_programme_staff_may_preview_a_case_they_will_teach():
    future = (date.today() + timedelta(days=30)).isoformat()
    result = _library().handle(
        {
            "reference": "lib-7",
            "status": "open",
            "track_id": "coo",
            "week": 1,
            "start_date": future,
            "timezone": "UTC",
            "session_offset": 2,
            "_roles": ["Faculty"],
        }
    )
    assert result["record"]["outcome_released"] is True


def test_the_case_class_date_comes_from_the_learners_calendar():
    start = date(2026, 9, 3)
    result = _library().handle(
        {
            "reference": "lib-4",
            "status": "open",
            "track_id": "coo",
            "week": 2,
            "start_date": start.isoformat(),
            "timezone": "Asia/Dubai",
            "session_offset": 0,
        }
    )
    expected = [
        entry for entry in schedule.generate(start, "Asia/Dubai", 2)
        if entry["week"] == 2 and entry["kind"] == "case_class"
    ][0]["local_date"]
    assert result["record"]["case_class_opens_on"] == expected


def test_a_week_the_track_does_not_declare_is_refused():
    result = _library().handle(
        {"reference": "lib-5", "status": "open", "track_id": "coo", "week": 99}
    )
    assert result["ok"] is False
    assert result["rejected_field"] == "week"
