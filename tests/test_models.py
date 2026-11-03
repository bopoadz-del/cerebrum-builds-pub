"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'claim_reference': 'sample', 'evidence_ref': 'sample', 'preparer_id': 'sample', 'certifier_id': 'sample', 'decision': 'sample', 'claim_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5}
    saved = store.save('claim_evidence_and_approvals', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for claim_evidence_and_approvals'
    fetched = store.get('claim_evidence_and_approvals', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'claim_evidence_and_approvals did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('claim_evidence_and_approvals', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'taking_over_date': '2026-09-03', 'defect_ref': 'sample', 'defect_description': 'sample', 'closeout_evidence': 'sample', 'retention_release_amount': 1.5}
    saved = store.save('defects_notification_period', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for defects_notification_period'
    fetched = store.get('defects_notification_period', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'defects_notification_period did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('defects_notification_period', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'accepted_contract_amount': 1.5, 'delay_days': 'email', 'delay_damages': 1.5, 'cap_reached': True}
    saved = store.save('delay_damages_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for delay_damages_tracking'
    fetched = store.get('delay_damages_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'delay_damages_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('delay_damages_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'title': 'sample', 'revision': 'sample', 'document_type': 'contract', 'source_filename': 'sample', 'checksum': 'sample', 'issued_date': '2026-09-03'}
    saved = store.save('document_register', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_register'
    fetched = store.get('document_register', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_register did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_register', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'instrument_number': 'sample', 'accepted_contract_amount': 1.5, 'security_amount': 1.5, 'expiry_date': '2026-09-03', 'issuer': 'sample'}
    saved = store.save('performance_security_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for performance_security_tracking'
    fetched = store.get('performance_security_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'performance_security_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('performance_security_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'period': 'sample', 'gross_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5, 'currency': 'sample'}
    saved = store.save('progress_claims', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for progress_claims'
    fetched = store.get('progress_claims', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'progress_claims did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('progress_claims', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'boq_item': 'sample', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'sample', 'inspection_date': '2026-09-03'}
    saved = store.save('qa_itp_records', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for qa_itp_records'
    fetched = store.get('qa_itp_records', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'qa_itp_records did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('qa_itp_records', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
