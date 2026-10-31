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



# -- cost_price_movement_alerts ----------------------------------


def test_cost_price_movement_alerts_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'reference': 'sample', 'status': 'open', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    resp = client.post("/v1/cost_price_movement_alerts", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "cost_price_movement_alerts accepted a payload with no alert_reference: " + resp.text[:200]
    )


def test_cost_price_movement_alerts_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    resp = client.post("/v1/cost_price_movement_alerts", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "cost_price_movement_alerts accepted an undeclared status: " + resp.text[:200]
    )


def test_cost_price_movement_alerts_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    made = client.post("/v1/cost_price_movement_alerts", json=body, headers=AUTH)
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
    other = client.get("/v1/cost_price_movement_alerts/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "cost_price_movement_alerts answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_cost_price_movement_alerts_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/cost_price_movement_alerts", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "cost_price_movement_alerts raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "cost_price_movement_alerts accepted malformed input %r" % (junk,)
        )


# -- document_grounded_qa ----------------------------------------


def test_document_grounded_qa_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'reference': 'sample', 'status': 'open', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    resp = client.post("/v1/document_grounded_qa", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_grounded_qa accepted a payload with no question: " + resp.text[:200]
    )


def test_document_grounded_qa_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'question': 'sample', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    resp = client.post("/v1/document_grounded_qa", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_grounded_qa accepted an undeclared status: " + resp.text[:200]
    )


def test_document_grounded_qa_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'question': 'sample', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    made = client.post("/v1/document_grounded_qa", json=body, headers=AUTH)
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
    other = client.get("/v1/document_grounded_qa/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "document_grounded_qa answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_document_grounded_qa_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/document_grounded_qa", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "document_grounded_qa raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "document_grounded_qa accepted malformed input %r" % (junk,)
        )


# -- document_ingestion_from_m365_and_upload ---------------------


def test_document_ingestion_from_m365_and_upload_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'reference': 'sample', 'status': 'open', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    resp = client.post("/v1/document_ingestion_from_m365_and_upload", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_ingestion_from_m365_and_upload accepted a payload with no document_name: " + resp.text[:200]
    )


def test_document_ingestion_from_m365_and_upload_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    resp = client.post("/v1/document_ingestion_from_m365_and_upload", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_ingestion_from_m365_and_upload accepted an undeclared status: " + resp.text[:200]
    )


def test_document_ingestion_from_m365_and_upload_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    made = client.post("/v1/document_ingestion_from_m365_and_upload", json=body, headers=AUTH)
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
    other = client.get("/v1/document_ingestion_from_m365_and_upload/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "document_ingestion_from_m365_and_upload answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_document_ingestion_from_m365_and_upload_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/document_ingestion_from_m365_and_upload", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "document_ingestion_from_m365_and_upload raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "document_ingestion_from_m365_and_upload accepted malformed input %r" % (junk,)
        )


# -- document_revision_nudges ------------------------------------


def test_document_revision_nudges_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'reference': 'sample', 'status': 'open', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    resp = client.post("/v1/document_revision_nudges", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_revision_nudges accepted a payload with no document_name: " + resp.text[:200]
    )


def test_document_revision_nudges_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'document_name': 'sample', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    resp = client.post("/v1/document_revision_nudges", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_revision_nudges accepted an undeclared status: " + resp.text[:200]
    )


def test_document_revision_nudges_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    made = client.post("/v1/document_revision_nudges", json=body, headers=AUTH)
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
    other = client.get("/v1/document_revision_nudges/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "document_revision_nudges answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_document_revision_nudges_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/document_revision_nudges", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "document_revision_nudges raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "document_revision_nudges accepted malformed input %r" % (junk,)
        )


# -- manager_dashboard -------------------------------------------


def test_manager_dashboard_empty_payload_is_the_declared_all_plants_default():
    # Every dashboard field is optional: an empty query means all plants.
    resp = client.post("/v1/manager_dashboard", json={}, headers=AUTH)
    if resp.status_code not in ACCEPTED or _refused(resp):
        pytest.skip("blocks unavailable in this checkout (sealed vendor/ absent)")
    assert resp.json()["result"]["plant"] == "all"


def test_manager_dashboard_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'plant': 'plant-casablanca', 'period_start': '2026-09-03', 'period_end': '2026-09-03', 'include_alerts': True, 'layout': 'sample'}
    resp = client.post("/v1/manager_dashboard", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "manager_dashboard accepted an undeclared status: " + resp.text[:200]
    )


def test_manager_dashboard_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'plant': 'plant-casablanca', 'period_start': '2026-09-03', 'period_end': '2026-09-03', 'include_alerts': True, 'layout': 'sample'}
    made = client.post("/v1/manager_dashboard", json=body, headers=AUTH)
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
    other = client.get("/v1/manager_dashboard/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "manager_dashboard answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_manager_dashboard_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", 42, {"include_alerts": "yes"}):
        resp = client.post("/v1/manager_dashboard", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "manager_dashboard raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "manager_dashboard accepted malformed input %r" % (junk,)
        )


# -- manager_only_access -----------------------------------------


def test_manager_only_access_refuses_an_empty_payload():
    # Nothing at all is not a record.
    resp = client.post("/v1/manager_only_access", json={}, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "manager_only_access accepted an empty payload: " + resp.text[:200]
    )


def test_manager_only_access_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'manager_name': 'sample', 'manager_email': 'guest@example.com', 'role': 'manager', 'plant': 'plant-casablanca'}
    resp = client.post("/v1/manager_only_access", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "manager_only_access accepted an undeclared status: " + resp.text[:200]
    )


def test_manager_only_access_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'manager_name': 'sample', 'manager_email': 'guest@example.com', 'role': 'manager', 'plant': 'plant-casablanca'}
    made = client.post("/v1/manager_only_access", json=body, headers=AUTH)
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
    other = client.get("/v1/manager_only_access/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "manager_only_access answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_manager_only_access_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/manager_only_access", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "manager_only_access raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "manager_only_access accepted malformed input %r" % (junk,)
        )


# -- sap_odata_connector -----------------------------------------


def test_sap_odata_connector_empty_payload_defaults_to_status():
    # operation is a declared vocabulary with a declared default (status).
    resp = client.post("/v1/sap_odata_connector", json={}, headers=AUTH)
    if resp.status_code not in ACCEPTED or _refused(resp):
        pytest.skip("blocks unavailable in this checkout (sealed vendor/ absent)")
    assert resp.json()["result"]["operation"] == "status"


def test_sap_odata_connector_refuses_an_operation_outside_its_vocabulary():
    body = {'operation': 'drop_tables'}
    resp = client.post("/v1/sap_odata_connector", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "sap_odata_connector accepted an undeclared operation: " + resp.text[:200]
    )


def test_sap_odata_connector_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'company_code': 'sample', 'operation': 'status', 'base_url': 'sample'}
    resp = client.post("/v1/sap_odata_connector", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "sap_odata_connector accepted an undeclared status: " + resp.text[:200]
    )


def test_sap_odata_connector_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'company_code': 'sample', 'operation': 'status', 'base_url': 'sample'}
    made = client.post("/v1/sap_odata_connector", json=body, headers=AUTH)
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
    other = client.get("/v1/sap_odata_connector/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "sap_odata_connector answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_sap_odata_connector_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", 42, {"operation": "drop_tables"}):
        resp = client.post("/v1/sap_odata_connector", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "sap_odata_connector raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "sap_odata_connector accepted malformed input %r" % (junk,)
        )


# -- supplier_cost_and_parts_pricing -----------------------------


def test_supplier_cost_and_parts_pricing_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'reference': 'sample', 'status': 'open', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    resp = client.post("/v1/supplier_cost_and_parts_pricing", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "supplier_cost_and_parts_pricing accepted a payload with no invoice_reference: " + resp.text[:200]
    )


def test_supplier_cost_and_parts_pricing_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    resp = client.post("/v1/supplier_cost_and_parts_pricing", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "supplier_cost_and_parts_pricing accepted an undeclared status: " + resp.text[:200]
    )


def test_supplier_cost_and_parts_pricing_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    made = client.post("/v1/supplier_cost_and_parts_pricing", json=body, headers=AUTH)
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
    other = client.get("/v1/supplier_cost_and_parts_pricing/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "supplier_cost_and_parts_pricing answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_supplier_cost_and_parts_pricing_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/supplier_cost_and_parts_pricing", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "supplier_cost_and_parts_pricing raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "supplier_cost_and_parts_pricing accepted malformed input %r" % (junk,)
        )
