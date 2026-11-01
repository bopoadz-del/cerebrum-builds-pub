"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import collection_planning_tracking
    assert collection_planning_tracking.CAPABILITY_ID
    from app.actions import batch_production_tracking
    assert batch_production_tracking.CAPABILITY_ID
    from app.actions import catalog_pricing_orders
    assert catalog_pricing_orders.CAPABILITY_ID
    from app.actions import invoicing_tunisian_vat
    assert invoicing_tunisian_vat.CAPABILITY_ID
    from app.actions import internal_staff_access
    assert internal_staff_access.CAPABILITY_ID
    from app.actions import operational_dashboard
    assert operational_dashboard.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['analytics', 'audit', 'auth', 'billing', 'dashboard', 'finance_canonical_model', 'finance_coa_governance', 'geolocation_tracking', 'multi_tenant_rbac', 'task_listing', 'vendor_catalog', 'workflow']:
        load_block(block_id)
    actions = {'analytics': 'track_event', 'audit': 'log', 'auth': 'validate', 'billing': 'record_usage', 'dashboard': 'render', 'workflow': 'run'}
    for block_id in ['analytics', 'audit', 'auth', 'billing', 'dashboard', 'finance_canonical_model', 'finance_coa_governance', 'geolocation_tracking', 'multi_tenant_rbac', 'task_listing', 'vendor_catalog', 'workflow']:
        try:
            result = execute(block_id, {}, action=actions.get(block_id))
        except RuntimeError as exc:
            # The block ran and refused the empty probe -- fine here;
            # the pilot test below demands Store-backed success.
            # An import error is never fine.
            assert "No module named" not in str(exc), (block_id, exc)
            assert "cannot import" not in str(exc), (block_id, exc)
        else:
            assert isinstance(result, dict), block_id


def test_kit_packs_present():
    """The download is a product tree: kits/ next to vendor/blocks."""
    from pathlib import Path as _Path
    kits = _Path(__file__).resolve().parents[1] / "kits"
    assert kits.is_dir(), "kits/ missing from the delivered platform"
    assert list(kits.glob("*/manifest.json")), "no kit pack manifests"


import json as _cap_json
import os as _cap_os


def _record_capability_failure(capability_id):
    """Factory suite only: note the capability this running test found
    failing (pytest names the test in PYTEST_CURRENT_TEST)."""
    path = _cap_os.environ.get('FACTORY_CAPABILITY_LOG')
    if not path or not capability_id:
        return
    running = _cap_os.environ.get("PYTEST_CURRENT_TEST") or ""
    test = running.rsplit(" (", 1)[0]
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_cap_json.dumps({"test": test, "capability": str(capability_id)}) + "\n")
    except OSError:
        pass


def test_every_capability_handle_returns_mapping():
    """Code-phase: the coder wired handle() and it returns a dict.
    Store ok: False or a Store exception is not this gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    failures = []
    from app.actions import collection_planning_tracking
    try:
        out = collection_planning_tracking.handle({'reference': 'sample', 'status': 'open', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('collection_planning_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('collection_planning_tracking')
    from app.actions import batch_production_tracking
    try:
        out = batch_production_tracking.handle({'reference': 'sample', 'status': 'open', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('batch_production_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('batch_production_tracking')
    from app.actions import catalog_pricing_orders
    try:
        out = catalog_pricing_orders.handle({'reference': 'sample', 'status': 'open', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('catalog_pricing_orders handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('catalog_pricing_orders')
    from app.actions import invoicing_tunisian_vat
    try:
        out = invoicing_tunisian_vat.handle({'reference': 'sample', 'status': 'open', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('invoicing_tunisian_vat handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('invoicing_tunisian_vat')
    from app.actions import internal_staff_access
    try:
        out = internal_staff_access.handle({'reference': 'sample', 'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('internal_staff_access handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('internal_staff_access')
    from app.actions import operational_dashboard
    try:
        out = operational_dashboard.handle({'reference': 'sample', 'status': 'open', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('operational_dashboard handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('operational_dashboard')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import collection_planning_tracking
    out = collection_planning_tracking.handle({'reference': 'sample', 'status': 'open', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('collection_planning_tracking returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('collection_planning_tracking')
    elif out.get('ok') is False:
        failures.append('collection_planning_tracking rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('collection_planning_tracking')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('collection_planning_tracking reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('collection_planning_tracking')
    from app.actions import batch_production_tracking
    out = batch_production_tracking.handle({'reference': 'sample', 'status': 'open', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('batch_production_tracking returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('batch_production_tracking')
    elif out.get('ok') is False:
        failures.append('batch_production_tracking rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('batch_production_tracking')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('batch_production_tracking reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('batch_production_tracking')
    from app.actions import catalog_pricing_orders
    out = catalog_pricing_orders.handle({'reference': 'sample', 'status': 'open', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('catalog_pricing_orders returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('catalog_pricing_orders')
    elif out.get('ok') is False:
        failures.append('catalog_pricing_orders rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('catalog_pricing_orders')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('catalog_pricing_orders reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('catalog_pricing_orders')
    from app.actions import invoicing_tunisian_vat
    out = invoicing_tunisian_vat.handle({'reference': 'sample', 'status': 'open', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('invoicing_tunisian_vat returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('invoicing_tunisian_vat')
    elif out.get('ok') is False:
        failures.append('invoicing_tunisian_vat rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('invoicing_tunisian_vat')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('invoicing_tunisian_vat reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('invoicing_tunisian_vat')
    from app.actions import internal_staff_access
    out = internal_staff_access.handle({'reference': 'sample', 'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('internal_staff_access returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('internal_staff_access')
    elif out.get('ok') is False:
        failures.append('internal_staff_access rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('internal_staff_access')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('internal_staff_access reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('internal_staff_access')
    from app.actions import operational_dashboard
    out = operational_dashboard.handle({'reference': 'sample', 'status': 'open', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'})
    if not isinstance(out, dict):
        failures.append('operational_dashboard returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('operational_dashboard')
    elif out.get('ok') is False:
        failures.append('operational_dashboard rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('operational_dashboard')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('operational_dashboard reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('operational_dashboard')
    assert not failures, "; ".join(failures)
