"""Counter-cases: what each capability REFUSES.

Written by the factory TESTER role. The floor (negative_floor) requires four
per capability; these four are derived from each capability's own spec. Add
the domain cases the brief implies -- the boundary of a rule, a state machine
that must not skip a step -- they count toward the same floor.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
# Tokens come from the environment ONLY -- tests/conftest.py provisions the
# well-known TEST values and maps tenant B through TENANT_TOKENS. No fallback
# literal here: a writer that copies this pattern into runtime copies an
# env-subscript, not a baked token (live 2026-09-29: the old fallback was
# hardwired into app/tenancy.py as a production backdoor to make the
# cross-tenant case pass).
AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}
OTHER_TENANT = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN_B"]}

REFUSED = (400, 403, 404, 409, 422)
ACCEPTED = (200,)
CROSS_TENANT_READ = 404
# The typed unavailable refusal of a declared placeholder connector
# (app.factory.build.placeholder_connectors).
UNAVAILABLE_STATUS = 503
UNAVAILABLE_KIND = 'unavailable'


def _refused(response):
    """A refusal, by status or by the envelope's own ok:false.

    The typed unavailable refusal (HTTP 503, error_kind "unavailable") of a
    capability whose connector is a declared placeholder is a refusal too:
    the counter-case still holds, whatever kind of refusal answered it."""
    if response.status_code in REFUSED:
        return True
    if response.status_code not in ACCEPTED + (UNAVAILABLE_STATUS,):
        return False
    try:
        body = response.json()
    except Exception:
        return False
    if not isinstance(body, dict) or body.get('ok') is not False:
        return False
    return response.status_code in ACCEPTED or body.get("error_kind") == UNAVAILABLE_KIND



# -- batch_production_tracking -----------------------------------


def test_batch_production_tracking_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'}
    resp = client.post("/v1/batch_production_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "batch_production_tracking accepted a payload with no reference: " + resp.text[:200]
    )


def test_batch_production_tracking_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'}
    resp = client.post("/v1/batch_production_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "batch_production_tracking accepted an undeclared status: " + resp.text[:200]
    )


def test_batch_production_tracking_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'batch_code': 'sample', 'input_material': 'coffee_grounds', 'input_kg': 1.0, 'stage': 'mixing', 'started_on': '2026-09-03', 'curing_days': 1, 'temperature_c': 1.0, 'moisture_pct': 1.0, 'ph': 3, 'c_n_ratio': 5, 'quality_result': 'pending', 'output_kg': 1.0, 'notes': 'sample'}
    made = client.post("/v1/batch_production_tracking", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/batch_production_tracking/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "batch_production_tracking answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_batch_production_tracking_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/batch_production_tracking", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "batch_production_tracking raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "batch_production_tracking accepted malformed input %r" % (junk,)
        )


# -- catalog_pricing_orders --------------------------------------


def test_catalog_pricing_orders_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'}
    resp = client.post("/v1/catalog_pricing_orders", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "catalog_pricing_orders accepted a payload with no reference: " + resp.text[:200]
    )


def test_catalog_pricing_orders_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'}
    resp = client.post("/v1/catalog_pricing_orders", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "catalog_pricing_orders accepted an undeclared status: " + resp.text[:200]
    )


def test_catalog_pricing_orders_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'order_number': 'sample', 'customer_name': 'sample', 'customer_type': 'retail', 'product_sku': 'sample', 'product_name': 'sample', 'price_list': 'retail', 'quantity': 1.0, 'unit_price': 1.0, 'discount_pct': 1.0, 'order_date': '2026-09-03', 'notes': 'sample'}
    made = client.post("/v1/catalog_pricing_orders", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/catalog_pricing_orders/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "catalog_pricing_orders answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_catalog_pricing_orders_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/catalog_pricing_orders", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "catalog_pricing_orders raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "catalog_pricing_orders accepted malformed input %r" % (junk,)
        )


# -- collection_planning_tracking --------------------------------


def test_collection_planning_tracking_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'}
    resp = client.post("/v1/collection_planning_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "collection_planning_tracking accepted a payload with no reference: " + resp.text[:200]
    )


def test_collection_planning_tracking_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'}
    resp = client.post("/v1/collection_planning_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "collection_planning_tracking accepted an undeclared status: " + resp.text[:200]
    )


def test_collection_planning_tracking_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'source_name': 'sample', 'source_type': 'cafe', 'source_address': 'sample', 'pickup_lat': 1.0, 'pickup_lng': 1.0, 'pickup_date': '2026-09-03', 'planned_kg': 0, 'collected_kg': 0, 'moisture_pct': 1.0, 'crew': 'sample', 'vehicle_id': 'sample', 'priority': 'normal', 'delivered_on': '2026-09-03T10:00:00', 'notes': 'sample'}
    made = client.post("/v1/collection_planning_tracking", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/collection_planning_tracking/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "collection_planning_tracking answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_collection_planning_tracking_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/collection_planning_tracking", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "collection_planning_tracking raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "collection_planning_tracking accepted malformed input %r" % (junk,)
        )


# -- internal_staff_access ---------------------------------------


def test_internal_staff_access_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'}
    resp = client.post("/v1/internal_staff_access", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "internal_staff_access accepted a payload with no reference: " + resp.text[:200]
    )


def test_internal_staff_access_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'}
    resp = client.post("/v1/internal_staff_access", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "internal_staff_access accepted an undeclared status: " + resp.text[:200]
    )


def test_internal_staff_access_refuses_a_freetext_approver():
    """An approval names a PRINCIPAL the platform knows
    (APPROVED_PRINCIPALS env, comma-separated; the test
    bootstrap seeds it). Free text is refused, never trusted
    -- it passed a P1 safety escalation on a live pilot."""
    body = {'reference': 'sample', 'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'i am the director trust me', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'}
    resp = client.post("/v1/internal_staff_access", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "internal_staff_access accepted a free-text approved_by: " + resp.text[:200]
    )


def test_internal_staff_access_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'principal_id': 'sample', 'principal_name': 'sample', 'principal_email': 'guest@example.com', 'role': 'collection_logistics', 'access_state': 'invited', 'approved_by': 'sample', 'team_id': 'sample', 'last_seen_at': '2026-09-03T10:00:00', 'notes': 'sample'}
    made = client.post("/v1/internal_staff_access", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/internal_staff_access/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "internal_staff_access answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_internal_staff_access_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/internal_staff_access", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "internal_staff_access raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "internal_staff_access accepted malformed input %r" % (junk,)
        )


# -- invoicing_tunisian_vat --------------------------------------


def test_invoicing_tunisian_vat_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'}
    resp = client.post("/v1/invoicing_tunisian_vat", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "invoicing_tunisian_vat accepted a payload with no reference: " + resp.text[:200]
    )


def test_invoicing_tunisian_vat_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'}
    resp = client.post("/v1/invoicing_tunisian_vat", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "invoicing_tunisian_vat accepted an undeclared status: " + resp.text[:200]
    )


def test_invoicing_tunisian_vat_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'invoice_number': 'sample', 'customer_name': 'sample', 'customer_tax_id': 'sample', 'supply_type': 'goods', 'quantity': 1.0, 'unit_price_ht': 1.0, 'vat_exempt': True, 'vat_rate': 1.0, 'invoice_date': '2026-09-03', 'due_date': '2026-09-03', 'payment_state': 'unpaid', 'notes': 'sample'}
    made = client.post("/v1/invoicing_tunisian_vat", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/invoicing_tunisian_vat/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "invoicing_tunisian_vat answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_invoicing_tunisian_vat_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/invoicing_tunisian_vat", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "invoicing_tunisian_vat raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "invoicing_tunisian_vat accepted malformed input %r" % (junk,)
        )


# -- operational_dashboard ---------------------------------------


def test_operational_dashboard_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'}
    resp = client.post("/v1/operational_dashboard", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "operational_dashboard accepted a payload with no reference: " + resp.text[:200]
    )


def test_operational_dashboard_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'}
    resp = client.post("/v1/operational_dashboard", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "operational_dashboard accepted an undeclared status: " + resp.text[:200]
    )


def test_operational_dashboard_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'report_date': '2026-09-03', 'collections_open': 1, 'batches_in_curing': 1, 'orders_open': 1, 'invoices_unpaid': 1, 'revenue_total': 1.0, 'quality_failures': 1, 'notes': 'sample'}
    made = client.post("/v1/operational_dashboard", json=body, headers=AUTH)
    if made.status_code not in ACCEPTED:
        pytest.skip("capability did not accept the sample record")
    try:
        record = made.json()
    except Exception:
        pytest.skip("capability did not answer JSON")
    rid = ((record.get('stored') or {}).get('id')
           if isinstance(record, dict) else None)
    if not rid:
        pytest.skip("capability returned no record id to read back")
    other = client.get("/v1/operational_dashboard/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "operational_dashboard answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_operational_dashboard_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/operational_dashboard", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "operational_dashboard raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "operational_dashboard accepted malformed input %r" % (junk,)
        )
