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



# -- ai_faculty_sessions -----------------------------------------


def test_ai_faculty_sessions_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'session_kind': 'framework', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'}
    resp = client.post("/v1/ai_faculty_sessions", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "ai_faculty_sessions accepted a payload with no reference: " + resp.text[:200]
    )


def test_ai_faculty_sessions_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'session_kind': 'not-a-declared-value', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'}
    resp = client.post("/v1/ai_faculty_sessions", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "ai_faculty_sessions accepted an undeclared session_kind: " + resp.text[:200]
    )


def test_ai_faculty_sessions_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'session_kind': 'framework', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'}
    made = client.post("/v1/ai_faculty_sessions", json=body, headers=AUTH)
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
    other = client.get("/v1/ai_faculty_sessions/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "ai_faculty_sessions answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_ai_faculty_sessions_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/ai_faculty_sessions", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "ai_faculty_sessions raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "ai_faculty_sessions accepted malformed input %r" % (junk,)
        )


# -- command_center_and_chat -------------------------------------


def test_command_center_and_chat_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'stage': 'enrol', 'message': 'sample', 'status': 'open'}
    resp = client.post("/v1/command_center_and_chat", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "command_center_and_chat accepted a payload with no reference: " + resp.text[:200]
    )


def test_command_center_and_chat_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'stage': 'not-a-declared-value', 'message': 'sample', 'status': 'open'}
    resp = client.post("/v1/command_center_and_chat", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "command_center_and_chat accepted an undeclared stage: " + resp.text[:200]
    )


def test_command_center_and_chat_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'stage': 'enrol', 'message': 'sample', 'status': 'open'}
    made = client.post("/v1/command_center_and_chat", json=body, headers=AUTH)
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
    other = client.get("/v1/command_center_and_chat/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "command_center_and_chat answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_command_center_and_chat_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/command_center_and_chat", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "command_center_and_chat raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "command_center_and_chat accepted malformed input %r" % (junk,)
        )


# -- defenses_and_capstone ---------------------------------------


def test_defenses_and_capstone_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'open'}
    resp = client.post("/v1/defenses_and_capstone", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "defenses_and_capstone accepted a payload with no reference: " + resp.text[:200]
    )


def test_defenses_and_capstone_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'not-a-declared-value'}
    resp = client.post("/v1/defenses_and_capstone", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "defenses_and_capstone accepted an undeclared status: " + resp.text[:200]
    )


def test_defenses_and_capstone_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'open'}
    made = client.post("/v1/defenses_and_capstone", json=body, headers=AUTH)
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
    other = client.get("/v1/defenses_and_capstone/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "defenses_and_capstone answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_defenses_and_capstone_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/defenses_and_capstone", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "defenses_and_capstone raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "defenses_and_capstone accepted malformed input %r" % (junk,)
        )


# -- enrolment_and_scheduling ------------------------------------


def test_enrolment_and_scheduling_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'open'}
    resp = client.post("/v1/enrolment_and_scheduling", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "enrolment_and_scheduling accepted a payload with no reference: " + resp.text[:200]
    )


def test_enrolment_and_scheduling_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'not-a-declared-value'}
    resp = client.post("/v1/enrolment_and_scheduling", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "enrolment_and_scheduling accepted an undeclared status: " + resp.text[:200]
    )


def test_enrolment_and_scheduling_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'open'}
    made = client.post("/v1/enrolment_and_scheduling", json=body, headers=AUTH)
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
    other = client.get("/v1/enrolment_and_scheduling/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "enrolment_and_scheduling answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_enrolment_and_scheduling_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/enrolment_and_scheduling", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "enrolment_and_scheduling raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "enrolment_and_scheduling accepted malformed input %r" % (junk,)
        )


# -- gradebook_and_transcript ------------------------------------


def test_gradebook_and_transcript_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'open'}
    resp = client.post("/v1/gradebook_and_transcript", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "gradebook_and_transcript accepted a payload with no reference: " + resp.text[:200]
    )


def test_gradebook_and_transcript_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'not-a-declared-value'}
    resp = client.post("/v1/gradebook_and_transcript", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "gradebook_and_transcript accepted an undeclared status: " + resp.text[:200]
    )


def test_gradebook_and_transcript_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'open'}
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


# -- library_surfaces --------------------------------------------


def test_library_surfaces_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'track_key': 'sample', 'week': 1, 'session_kind': 'framework', 'query': 'sample', 'status': 'open'}
    resp = client.post("/v1/library_surfaces", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "library_surfaces accepted a payload with no reference: " + resp.text[:200]
    )


def test_library_surfaces_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'track_key': 'sample', 'week': 1, 'session_kind': 'not-a-declared-value', 'query': 'sample', 'status': 'open'}
    resp = client.post("/v1/library_surfaces", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "library_surfaces accepted an undeclared session_kind: " + resp.text[:200]
    )


def test_library_surfaces_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'track_key': 'sample', 'week': 1, 'session_kind': 'framework', 'query': 'sample', 'status': 'open'}
    made = client.post("/v1/library_surfaces", json=body, headers=AUTH)
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
    other = client.get("/v1/library_surfaces/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "library_surfaces answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_library_surfaces_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/library_surfaces", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "library_surfaces raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "library_surfaces accepted malformed input %r" % (junk,)
        )


# -- memo_grading ------------------------------------------------


def test_memo_grading_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'open'}
    resp = client.post("/v1/memo_grading", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "memo_grading accepted a payload with no reference: " + resp.text[:200]
    )


def test_memo_grading_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'not-a-declared-value'}
    resp = client.post("/v1/memo_grading", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "memo_grading accepted an undeclared status: " + resp.text[:200]
    )


def test_memo_grading_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'open'}
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


# -- track_management --------------------------------------------


def test_track_management_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'open'}
    resp = client.post("/v1/track_management", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_management accepted a payload with no reference: " + resp.text[:200]
    )


def test_track_management_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'not-a-declared-value'}
    resp = client.post("/v1/track_management", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "track_management accepted an undeclared status: " + resp.text[:200]
    )


def test_track_management_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'open'}
    made = client.post("/v1/track_management", json=body, headers=AUTH)
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
    other = client.get("/v1/track_management/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "track_management answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_track_management_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/track_management", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "track_management raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "track_management accepted malformed input %r" % (junk,)
        )
