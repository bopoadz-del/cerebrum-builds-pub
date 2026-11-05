"""Counter-cases: what each capability REFUSES.

Written by the factory TESTER role. The floor (negative_floor) requires four
per capability; these four are derived from each capability's own spec. Add
the domain cases the brief implies -- the boundary of a rule, a state machine
that must not skip a step -- they count toward the same floor.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
# Tokens come from the environment ONLY -- tests/conftest.py provisions the
# well-known TEST values and maps tenant B through TENANT_TOKENS. No fallback
# literal here: a writer that copies this pattern into runtime copies an
# env-subscript, not a baked token (live 2026-09-29: the old fallback was
# hardwired into app/tenancy.py as a production backdoor to make the
# cross-tenant case pass).
AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
OTHER_TENANT = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN_B"]}

REFUSED = (400, 403, 404, 409, 422)
ACCEPTED = (200,)
CROSS_TENANT_READ = 404
# The typed unavailable refusal of a declared placeholder connector
# (app.factory.build.placeholder_connectors).
UNAVAILABLE_STATUS = 503
UNAVAILABLE_KIND = 'unavailable'


def _refused(response):
    """A refusal, by status or by the envelope's own ok:false.

    The typed unavailable refusal (HTTP 503, error_kind "unavailable") of a
    capability whose connector is a declared placeholder is a refusal too:
    the counter-case still holds, whatever kind of refusal answered it."""
    if response.status_code in REFUSED:
        return True
    if response.status_code not in ACCEPTED + (UNAVAILABLE_STATUS,):
        return False
    try:
        body = response.json()
    except Exception:
        return False
    if not isinstance(body, dict) or body.get('ok') is not False:
        return False
    return response.status_code in ACCEPTED or body.get("error_kind") == UNAVAILABLE_KIND



# -- defense_and_capstone ----------------------------------------


def test_defense_and_capstone_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    resp = client.post("/v1/defense_and_capstone", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "defense_and_capstone accepted a payload with no reference: " + resp.text[:200]
    )


def test_defense_and_capstone_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    resp = client.post("/v1/defense_and_capstone", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "defense_and_capstone accepted an undeclared status: " + resp.text[:200]
    )


def test_defense_and_capstone_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    made = client.post("/v1/defense_and_capstone", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/defense_and_capstone/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "defense_and_capstone answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_defense_and_capstone_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/defense_and_capstone", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "defense_and_capstone raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "defense_and_capstone accepted malformed input %r" % (junk,)
        )


# -- enrolment_and_calendar --------------------------------------


def test_enrolment_and_calendar_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    resp = client.post("/v1/enrolment_and_calendar", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "enrolment_and_calendar accepted a payload with no reference: " + resp.text[:200]
    )


def test_enrolment_and_calendar_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    resp = client.post("/v1/enrolment_and_calendar", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "enrolment_and_calendar accepted an undeclared status: " + resp.text[:200]
    )


def test_enrolment_and_calendar_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    made = client.post("/v1/enrolment_and_calendar", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/enrolment_and_calendar/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "enrolment_and_calendar answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_enrolment_and_calendar_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/enrolment_and_calendar", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "enrolment_and_calendar raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "enrolment_and_calendar accepted malformed input %r" % (junk,)
        )


# -- faculty_session ---------------------------------------------


def test_faculty_session_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    resp = client.post("/v1/faculty_session", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "faculty_session accepted a payload with no reference: " + resp.text[:200]
    )


def test_faculty_session_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    resp = client.post("/v1/faculty_session", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "faculty_session accepted an undeclared status: " + resp.text[:200]
    )


def test_faculty_session_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    made = client.post("/v1/faculty_session", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/faculty_session/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "faculty_session answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_faculty_session_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/faculty_session", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "faculty_session raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "faculty_session accepted malformed input %r" % (junk,)
        )


# -- gradebook_and_transcript ------------------------------------


def test_gradebook_and_transcript_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    resp = client.post("/v1/gradebook_and_transcript", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "gradebook_and_transcript accepted a payload with no reference: " + resp.text[:200]
    )


def test_gradebook_and_transcript_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    resp = client.post("/v1/gradebook_and_transcript", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "gradebook_and_transcript accepted an undeclared status: " + resp.text[:200]
    )


def test_gradebook_and_transcript_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    made = client.post("/v1/gradebook_and_transcript", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/gradebook_and_transcript/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "gradebook_and_transcript answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_gradebook_and_transcript_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/gradebook_and_transcript", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "gradebook_and_transcript raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "gradebook_and_transcript accepted malformed input %r" % (junk,)
        )


# -- memo_grading ------------------------------------------------


def test_memo_grading_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    resp = client.post("/v1/memo_grading", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "memo_grading accepted a payload with no reference: " + resp.text[:200]
    )


def test_memo_grading_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    resp = client.post("/v1/memo_grading", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "memo_grading accepted an undeclared status: " + resp.text[:200]
    )


def test_memo_grading_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    made = client.post("/v1/memo_grading", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/memo_grading/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "memo_grading answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_memo_grading_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/memo_grading", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "memo_grading raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "memo_grading accepted malformed input %r" % (junk,)
        )


# -- reading_and_case_library ------------------------------------


def test_reading_and_case_library_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    resp = client.post("/v1/reading_and_case_library", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "reading_and_case_library accepted a payload with no reference: " + resp.text[:200]
    )


def test_reading_and_case_library_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    resp = client.post("/v1/reading_and_case_library", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "reading_and_case_library accepted an undeclared status: " + resp.text[:200]
    )


def test_reading_and_case_library_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    made = client.post("/v1/reading_and_case_library", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/reading_and_case_library/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "reading_and_case_library answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_reading_and_case_library_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/reading_and_case_library", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "reading_and_case_library raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "reading_and_case_library accepted malformed input %r" % (junk,)
        )


# -- track_admin -------------------------------------------------


def test_track_admin_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'}
    resp = client.post("/v1/track_admin", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_admin accepted a payload with no reference: " + resp.text[:200]
    )


def test_track_admin_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'operation': 'validate', 'pinned_version': 'sample'}
    resp = client.post("/v1/track_admin", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_admin accepted an undeclared status: " + resp.text[:200]
    )


def test_track_admin_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'}
    made = client.post("/v1/track_admin", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/track_admin/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "track_admin answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_track_admin_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/track_admin", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "track_admin raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "track_admin accepted malformed input %r" % (junk,)
        )


# -- track_loader ------------------------------------------------


def test_track_loader_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'schema_version': 'sample'}
    resp = client.post("/v1/track_loader", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_loader accepted a payload with no reference: " + resp.text[:200]
    )


def test_track_loader_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'schema_version': 'sample'}
    resp = client.post("/v1/track_loader", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_loader accepted an undeclared status: " + resp.text[:200]
    )


def test_track_loader_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'schema_version': 'sample'}
    made = client.post("/v1/track_loader", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/track_loader/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "track_loader answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_track_loader_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/track_loader", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "track_loader raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "track_loader accepted malformed input %r" % (junk,)
        )
