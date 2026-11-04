"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'session_kind': 'framework', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'}
    saved = store.save('ai_faculty_sessions', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for ai_faculty_sessions'
    fetched = store.get('ai_faculty_sessions', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'ai_faculty_sessions did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('ai_faculty_sessions', tenant_id=TENANT))
    record = {'reference': 'sample', 'stage': 'enrol', 'message': 'sample', 'status': 'open'}
    saved = store.save('command_center_and_chat', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for command_center_and_chat'
    fetched = store.get('command_center_and_chat', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'command_center_and_chat did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('command_center_and_chat', tenant_id=TENANT))
    record = {'reference': 'sample', 'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'open'}
    saved = store.save('defenses_and_capstone', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for defenses_and_capstone'
    fetched = store.get('defenses_and_capstone', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'defenses_and_capstone did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('defenses_and_capstone', tenant_id=TENANT))
    record = {'reference': 'sample', 'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'open'}
    saved = store.save('enrolment_and_scheduling', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for enrolment_and_scheduling'
    fetched = store.get('enrolment_and_scheduling', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'enrolment_and_scheduling did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('enrolment_and_scheduling', tenant_id=TENANT))
    record = {'reference': 'sample', 'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'open'}
    saved = store.save('gradebook_and_transcript', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for gradebook_and_transcript'
    fetched = store.get('gradebook_and_transcript', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'gradebook_and_transcript did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('gradebook_and_transcript', tenant_id=TENANT))
    record = {'reference': 'sample', 'track_key': 'sample', 'week': 1, 'session_kind': 'framework', 'query': 'sample', 'status': 'open'}
    saved = store.save('library_surfaces', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for library_surfaces'
    fetched = store.get('library_surfaces', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'library_surfaces did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('library_surfaces', tenant_id=TENANT))
    record = {'reference': 'sample', 'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'open'}
    saved = store.save('memo_grading', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for memo_grading'
    fetched = store.get('memo_grading', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'memo_grading did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('memo_grading', tenant_id=TENANT))
    record = {'reference': 'sample', 'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'open'}
    saved = store.save('track_management', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for track_management'
    fetched = store.get('track_management', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'track_management did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('track_management', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
