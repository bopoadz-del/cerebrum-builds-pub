"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'}
    saved = store.save('delay_damages_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for delay_damages_tracking'
    fetched = store.get('delay_damages_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'delay_damages_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('delay_damages_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'}
    saved = store.save('document_register', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_register'
    fetched = store.get('document_register', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_register did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_register', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'}
    saved = store.save('progress_claim_administration', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for progress_claim_administration'
    fetched = store.get('progress_claim_administration', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'progress_claim_administration did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('progress_claim_administration', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'}
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
