"""Models must survive a round trip through sqlite."""

from app import store
from app.models import MODELS


#: Tenant the generated tests act as (the platform token's tenant).
TENANT = 'local'


def test_every_model_round_trips():
    record = {'reference': 'sample', 'status': 'open', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'}
    saved = store.save('batch_production_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for batch_production_tracking'
    fetched = store.get('batch_production_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'batch_production_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('batch_production_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'}
    saved = store.save('catalog_pricing_orders', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for catalog_pricing_orders'
    fetched = store.get('catalog_pricing_orders', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'catalog_pricing_orders did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('catalog_pricing_orders', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'}
    saved = store.save('collection_planning_tracking', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for collection_planning_tracking'
    fetched = store.get('collection_planning_tracking', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'collection_planning_tracking did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('collection_planning_tracking', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'}
    saved = store.save('internal_staff_access', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for internal_staff_access'
    fetched = store.get('internal_staff_access', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'internal_staff_access did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('internal_staff_access', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'}
    saved = store.save('invoicing_tunisian_vat', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for invoicing_tunisian_vat'
    fetched = store.get('invoicing_tunisian_vat', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'invoicing_tunisian_vat did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('invoicing_tunisian_vat', tenant_id=TENANT))
    record = {'reference': 'sample', 'status': 'open', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'}
    saved = store.save('operational_dashboard', record, tenant_id=TENANT)
    assert saved['id'] is not None, 'no id assigned for operational_dashboard'
    fetched = store.get('operational_dashboard', saved['id'], tenant_id=TENANT)
    assert fetched is not None, 'operational_dashboard did not persist'
    for key, value in record.items():
        assert fetched[key] == value, (key, fetched[key], value)
    assert any(r['id'] == saved['id'] for r in store.list_all('operational_dashboard', tenant_id=TENANT))


def test_models_expose_their_fields():
    assert MODELS, 'no models were generated'
    for cap_id, cls in MODELS.items():
        instance = cls.from_dict({})
        assert instance.to_dict()['id'] is None
        assert cls.FIELDS, cap_id
