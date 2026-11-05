"""Counter-cases: what each capability must refuse.

Proving the platform does the right thing is half a suite; this file proves
it refuses the wrong thing. Each test names the capability it measures, and
each assertion is a refusal: a 4xx, a typed ok:false, or a raised error from
the domain layer.
"""

from __future__ import annotations

import pytest

from app import schedule, track_schema


# --------------------------------------------------------------------------
# track_loader
# --------------------------------------------------------------------------
def test_track_loader_refuses_bad_inputs(client, auth, auth_b):
    missing = client.post("/v1/track_loader", json={"status": "open"}, headers=auth)
    assert missing.status_code == 422
    assert missing.json()["rejected_field"] == "reference"

    bad_vocabulary = client.post(
        "/v1/track_loader", json={"reference": "r", "status": "archived"}, headers=auth
    )
    assert bad_vocabulary.status_code == 422

    anonymous = client.post("/v1/track_loader", json={"reference": "r", "status": "open"})
    assert anonymous.status_code == 401

    created = client.post(
        "/v1/track_loader", json={"reference": "r-1", "status": "open"}, headers=auth
    )
    record_id = created.json()["id"]
    other_tenant = client.get("/v1/track_loader/%s" % record_id, headers=auth_b)
    assert other_tenant.status_code == 404

    outside_tracks = client.post(
        "/v1/track_loader",
        json={"reference": "r-2", "status": "open", "track_path": "../../etc/passwd"},
        headers=auth,
    )
    assert outside_tracks.json()["ok"] is False


# --------------------------------------------------------------------------
# enrolment_and_calendar (declared placeholder: the route refuses the send)
# --------------------------------------------------------------------------
def test_enrolment_and_calendar_refuses_bad_inputs(client, auth, auth_b):
    anonymous = client.post("/v1/enrolment_and_calendar", json={})
    assert anonymous.status_code == 401

    refused = client.post(
        "/v1/enrolment_and_calendar",
        json={"reference": "e-1", "status": "open"},
        headers=auth,
    )
    assert refused.status_code == 503
    assert refused.json()["settings"] == ["EMAIL_DELIVERY_CREDENTIALS"]

    with pytest.raises(schedule.ScheduleError):
        schedule.generate("2026-09-03", "Mars/Olympus_Mons", 16)
    with pytest.raises(schedule.ScheduleError):
        schedule.generate("the third of September", "UTC", 16)
    with pytest.raises(schedule.ScheduleError):
        schedule.zone("Not/AZone")

    absent = client.get("/v1/enrolment_and_calendar/999999", headers=auth_b)
    assert absent.status_code == 404


# --------------------------------------------------------------------------
# faculty_session
# --------------------------------------------------------------------------
def test_faculty_session_refuses_bad_inputs(client, auth, auth_b):
    unknown_mode = client.post(
        "/v1/faculty_session",
        json={"reference": "s-1", "status": "open", "mode": "seminar"},
        headers=auth,
    )
    assert unknown_mode.status_code == 422
    assert unknown_mode.json()["rejected_field"] == "mode"

    missing_reference = client.post(
        "/v1/faculty_session", json={"status": "open", "mode": "lecture"}, headers=auth
    )
    assert missing_reference.status_code == 422

    anonymous = client.post("/v1/faculty_session", json={})
    assert anonymous.status_code == 401

    out_of_range_week = client.post(
        "/v1/faculty_session",
        json={"reference": "s-2", "status": "open", "mode": "lecture", "week": 0},
        headers=auth,
    )
    assert out_of_range_week.status_code == 422

    other_tenant = client.get("/v1/faculty_session/999999", headers=auth_b)
    assert other_tenant.status_code == 404


# --------------------------------------------------------------------------
# memo_grading
# --------------------------------------------------------------------------
def test_memo_grading_refuses_bad_inputs(client, auth, auth_b):
    missing = client.post("/v1/memo_grading", json={"status": "open"}, headers=auth)
    assert missing.status_code == 422

    bad_week = client.post(
        "/v1/memo_grading",
        json={"reference": "m-1", "status": "open", "week": -2},
        headers=auth,
    )
    assert bad_week.status_code == 422

    anonymous = client.post("/v1/memo_grading", json={})
    assert anonymous.status_code == 401

    created = client.post(
        "/v1/memo_grading", json={"reference": "m-2", "status": "open", "week": 1}, headers=auth
    )
    assert created.json()["ok"] is True
    record_id = created.json()["id"]
    other_tenant = client.get("/v1/memo_grading/%s" % record_id, headers=auth_b)
    assert other_tenant.status_code == 404

    unknown_track = client.post(
        "/v1/memo_grading",
        json={"reference": "m-3", "status": "open", "track_id": "no-such-track"},
        headers=auth,
    )
    assert unknown_track.json()["ok"] is False


# --------------------------------------------------------------------------
# gradebook_and_transcript
# --------------------------------------------------------------------------
def test_gradebook_and_transcript_refuses_bad_inputs(client, auth, auth_b):
    above_range = client.post(
        "/v1/gradebook_and_transcript",
        json={"reference": "g-1", "status": "open", "memos_score": 101},
        headers=auth,
    )
    assert above_range.status_code == 422

    below_range = client.post(
        "/v1/gradebook_and_transcript",
        json={"reference": "g-2", "status": "open", "capstone_score": -1},
        headers=auth,
    )
    assert below_range.status_code == 422

    anonymous = client.post("/v1/gradebook_and_transcript", json={})
    assert anonymous.status_code == 401

    other_tenant = client.get("/v1/gradebook_and_transcript/999999", headers=auth_b)
    assert other_tenant.status_code == 404

    boundary = client.post(
        "/v1/gradebook_and_transcript",
        json={"reference": "g-3", "status": "open", "memos_score": 100},
        headers=auth,
    )
    assert boundary.json()["ok"] is True


# --------------------------------------------------------------------------
# defense_and_capstone (declared placeholder: the route refuses the invite)
# --------------------------------------------------------------------------
def test_defense_and_capstone_refuses_bad_inputs(client, auth, auth_b):
    anonymous = client.post("/v1/defense_and_capstone", json={})
    assert anonymous.status_code == 401

    refused = client.post(
        "/v1/defense_and_capstone",
        json={"reference": "d-1", "status": "open"},
        headers=auth,
    )
    assert refused.status_code == 503

    missing = client.get("/v1/defense_and_capstone/999999", headers=auth)
    assert missing.status_code == 404

    other_tenant = client.get("/v1/defense_and_capstone/999998", headers=auth_b)
    assert other_tenant.status_code == 404

    unknown_term = client.delete("/v1/defense_and_capstone/999997", headers=auth)
    assert unknown_term.status_code == 404


# --------------------------------------------------------------------------
# track_admin
# --------------------------------------------------------------------------
def test_track_admin_refuses_bad_inputs(client, auth, auth_b):
    bad_operation = client.post(
        "/v1/track_admin",
        json={"reference": "a-1", "status": "open", "operation": "delete-everything"},
        headers=auth,
    )
    assert bad_operation.status_code == 422

    missing = client.post("/v1/track_admin", json={"status": "open"}, headers=auth)
    assert missing.status_code == 422

    anonymous = client.post("/v1/track_admin", json={})
    assert anonymous.status_code == 401

    # tenant-b authenticates as Faculty: track administration is not theirs
    forbidden = client.post(
        "/v1/track_admin",
        json={"reference": "a-2", "status": "open"},
        headers=auth_b,
    )
    assert forbidden.status_code == 403

    other_tenant = client.get("/v1/track_admin/999999", headers=auth_b)
    assert other_tenant.status_code == 404


# --------------------------------------------------------------------------
# reading_and_case_library
# --------------------------------------------------------------------------
def test_reading_and_case_library_refuses_bad_inputs(client, auth, auth_b):
    bad_week = client.post(
        "/v1/reading_and_case_library",
        json={"reference": "l-1", "status": "open", "week": 0},
        headers=auth,
    )
    assert bad_week.status_code == 422

    missing = client.post(
        "/v1/reading_and_case_library", json={"status": "open"}, headers=auth
    )
    assert missing.status_code == 422

    anonymous = client.post("/v1/reading_and_case_library", json={})
    assert anonymous.status_code == 401

    out_of_range_week = client.post(
        "/v1/reading_and_case_library",
        json={"reference": "l-2", "status": "open", "week": 99},
        headers=auth,
    )
    assert out_of_range_week.json()["ok"] is False

    other_tenant = client.get("/v1/reading_and_case_library/999999", headers=auth_b)
    assert other_tenant.status_code == 404
