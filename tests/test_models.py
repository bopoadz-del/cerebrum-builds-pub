"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    saved = store.save('defense_and_capstone', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for defense_and_capstone'
    fetched = store.get('defense_and_capstone', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'defense_and_capstone did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('defense_and_capstone', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    saved = store.save('enrolment_and_calendar', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for enrolment_and_calendar'
    fetched = store.get('enrolment_and_calendar', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'enrolment_and_calendar did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('enrolment_and_calendar', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    saved = store.save('faculty_session', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for faculty_session'
    fetched = store.get('faculty_session', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'faculty_session did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('faculty_session', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    saved = store.save('gradebook_and_transcript', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for gradebook_and_transcript'
    fetched = store.get('gradebook_and_transcript', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'gradebook_and_transcript did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('gradebook_and_transcript', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    saved = store.save('memo_grading', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for memo_grading'
    fetched = store.get('memo_grading', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'memo_grading did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('memo_grading', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    saved = store.save('reading_and_case_library', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for reading_and_case_library'
    fetched = store.get('reading_and_case_library', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'reading_and_case_library did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('reading_and_case_library', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'}
    saved = store.save('track_admin', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for track_admin'
    fetched = store.get('track_admin', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'track_admin did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('track_admin', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'schema_version': 'sample'}
    saved = store.save('track_loader', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for track_loader'
    fetched = store.get('track_loader', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'track_loader did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('track_loader', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
