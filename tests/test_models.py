"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'subject_type': 'claim', 'subject_reference': 'sample', 'clause_ref': '8.2', 'boq_item_code': 'P1', 'evidence': 'sample', 'decision': 'verify'}
    saved = store.save('contract_verification_gate', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for contract_verification_gate'
    fetched = store.get('contract_verification_gate', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'contract_verification_gate did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('contract_verification_gate', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'assessment_number': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'days_of_delay': 1, 'accepted_contract_amount': 1.0, 'notice_served': True, 'assessment_note': 'sample'}
    saved = store.save('delay_damages_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for delay_damages_tracking'
    fetched = store.get('delay_damages_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'delay_damages_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('delay_damages_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'document_number': 'sample', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'source_document': 'document:e8ed082091b444d2ba20f217fd13d15a_harbourline_contract.pdf', 'checksum': 'sample', 'issued_date': '2026-09-03', 'supersedes': 'sample'}
    saved = store.save('document_register', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_register'
    fetched = store.get('document_register', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_register did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_register', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'claim_period': 'sample', 'boq_item_code': 'P1', 'measured_quantity': 1.0, 'unit_rate': 1.0, 'accepted_contract_amount': 1.0, 'approval_decision': 'none', 'approved_by': 'sample', 'certificate_note': 'sample'}
    saved = store.save('progress_claims', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for progress_claims'
    fetched = store.get('progress_claims', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'progress_claims did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('progress_claims', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'boq_item_code': 'P1', 'inspection_type': 'material', 'hold_point': True, 'inspection_date': '2026-09-03', 'result': 'pending', 'signed_off_by': 'sample', 'remarks': 'sample'}
    saved = store.save('qa_itp_records', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for qa_itp_records'
    fetched = store.get('qa_itp_records', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'qa_itp_records did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('qa_itp_records', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'certificate_reference': 'sample', 'gross_certified_amount': 1.0, 'taking_over_date': '2026-09-03', 'defects_notification_end_date': '2026-09-03', 'release_stage': 'taking_over', 'approval_decision': 'none', 'approved_by': 'sample', 'performance_security_amount': 1.0}
    saved = store.save('retention_defects_release', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for retention_defects_release'
    fetched = store.get('retention_defects_release', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'retention_defects_release did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('retention_defects_release', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
