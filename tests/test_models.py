"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1}
    saved = store.save('claims_analytics_dashboard', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for claims_analytics_dashboard'
    fetched = store.get('claims_analytics_dashboard', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'claims_analytics_dashboard did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('claims_analytics_dashboard', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'}
    saved = store.save('contract_clause_governance', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for contract_clause_governance'
    fetched = store.get('contract_clause_governance', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'contract_clause_governance did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('contract_clause_governance', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0}
    saved = store.save('delay_damages_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for delay_damages_tracking'
    fetched = store.get('delay_damages_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'delay_damages_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('delay_damages_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'}
    saved = store.save('document_register', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_register'
    fetched = store.get('document_register', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_register did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_register', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'}
    saved = store.save('payment_security_and_retention_ledger', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for payment_security_and_retention_ledger'
    fetched = store.get('payment_security_and_retention_ledger', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'payment_security_and_retention_ledger did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('payment_security_and_retention_ledger', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'}
    saved = store.save('progress_claims', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for progress_claims'
    fetched = store.get('progress_claims', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'progress_claims did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('progress_claims', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'}
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
