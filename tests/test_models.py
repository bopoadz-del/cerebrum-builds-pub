"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'source_document': 'document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'}
    saved = store.save('contract_source_of_record', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for contract_source_of_record'
    fetched = store.get('contract_source_of_record', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'contract_source_of_record did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('contract_source_of_record', tenant_id=TENANT))
    record = {'reference': 'sample', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'}
    saved = store.save('document_register', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_register'
    fetched = store.get('document_register', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_register did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_register', tenant_id=TENANT))
    record = {'reference': 'sample', 'ipc_number': 'sample', 'boq_item': 'P1', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'}
    saved = store.save('progress_claims', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for progress_claims'
    fetched = store.get('progress_claims', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'progress_claims did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('progress_claims', tenant_id=TENANT))
    record = {'reference': 'sample', 'boq_item': 'P1', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'}
    saved = store.save('qa_itp_records', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for qa_itp_records'
    fetched = store.get('qa_itp_records', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'qa_itp_records did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('qa_itp_records', tenant_id=TENANT))
    record = {'reference': 'sample', 'principal_id': 'sample', 'role': 'owner', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'}
    saved = store.save('role_based_access_and_audit', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for role_based_access_and_audit'
    fetched = store.get('role_based_access_and_audit', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'role_based_access_and_audit did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('role_based_access_and_audit', tenant_id=TENANT))
    record = {'reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'open'}
    saved = store.save('time_and_delay_damages', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for time_and_delay_damages'
    fetched = store.get('time_and_delay_damages', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'time_and_delay_damages did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('time_and_delay_damages', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
