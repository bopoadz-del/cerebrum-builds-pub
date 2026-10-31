"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    saved = store.save('cost_price_movement_alerts', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for cost_price_movement_alerts'
    fetched = store.get('cost_price_movement_alerts', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'cost_price_movement_alerts did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('cost_price_movement_alerts', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'question': 'sample', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    saved = store.save('document_grounded_qa', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_grounded_qa'
    fetched = store.get('document_grounded_qa', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_grounded_qa did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_grounded_qa', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    saved = store.save('document_ingestion_from_m365_and_upload', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_ingestion_from_m365_and_upload'
    fetched = store.get('document_ingestion_from_m365_and_upload', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_ingestion_from_m365_and_upload did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_ingestion_from_m365_and_upload', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    saved = store.save('document_revision_nudges', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for document_revision_nudges'
    fetched = store.get('document_revision_nudges', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'document_revision_nudges did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('document_revision_nudges', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'plant': 'plant-casablanca', 'period_start': '2026-09-03', 'period_end': '2026-09-03', 'include_alerts': True, 'layout': 'sample'}
    saved = store.save('manager_dashboard', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for manager_dashboard'
    fetched = store.get('manager_dashboard', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'manager_dashboard did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('manager_dashboard', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'manager_name': 'sample', 'manager_email': 'guest@example.com', 'role': 'manager', 'plant': 'plant-casablanca'}
    saved = store.save('manager_only_access', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for manager_only_access'
    fetched = store.get('manager_only_access', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'manager_only_access did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('manager_only_access', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'company_code': 'sample', 'operation': 'status', 'base_url': 'sample'}
    saved = store.save('sap_odata_connector', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for sap_odata_connector'
    fetched = store.get('sap_odata_connector', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'sap_odata_connector did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('sap_odata_connector', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    saved = store.save('supplier_cost_and_parts_pricing', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for supplier_cost_and_parts_pricing'
    fetched = store.get('supplier_cost_and_parts_pricing', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'supplier_cost_and_parts_pricing did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('supplier_cost_and_parts_pricing', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
