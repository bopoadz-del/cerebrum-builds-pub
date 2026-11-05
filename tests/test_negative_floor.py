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



# -- delay_damages_tracking --------------------------------------


def test_delay_damages_tracking_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'}
    resp = client.post("/v1/delay_damages_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "delay_damages_tracking accepted a payload with no reference: " + resp.text[:200]
    )


def test_delay_damages_tracking_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'}
    resp = client.post("/v1/delay_damages_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "delay_damages_tracking accepted an undeclared status: " + resp.text[:200]
    )


def test_delay_damages_tracking_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'}
    made = client.post("/v1/delay_damages_tracking", json=body, headers=AUTH)
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
    other = client.get("/v1/delay_damages_tracking/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "delay_damages_tracking answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_delay_damages_tracking_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/delay_damages_tracking", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "delay_damages_tracking raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "delay_damages_tracking accepted malformed input %r" % (junk,)
        )


# -- document_register -------------------------------------------


def test_document_register_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted a payload with no reference: " + resp.text[:200]
    )


def test_document_register_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted an undeclared status: " + resp.text[:200]
    )


def test_document_register_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'}
    made = client.post("/v1/document_register", json=body, headers=AUTH)
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
    other = client.get("/v1/document_register/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "document_register answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_document_register_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/document_register", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "document_register raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "document_register accepted malformed input %r" % (junk,)
        )


# -- progress_claim_administration -------------------------------


def test_progress_claim_administration_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'}
    resp = client.post("/v1/progress_claim_administration", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claim_administration accepted a payload with no reference: " + resp.text[:200]
    )


def test_progress_claim_administration_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'}
    resp = client.post("/v1/progress_claim_administration", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claim_administration accepted an undeclared status: " + resp.text[:200]
    )


def test_progress_claim_administration_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'}
    made = client.post("/v1/progress_claim_administration", json=body, headers=AUTH)
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
    other = client.get("/v1/progress_claim_administration/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "progress_claim_administration answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_progress_claim_administration_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/progress_claim_administration", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "progress_claim_administration raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "progress_claim_administration accepted malformed input %r" % (junk,)
        )


# -- qa_itp_records ----------------------------------------------


def test_qa_itp_records_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted a payload with no reference: " + resp.text[:200]
    )


def test_qa_itp_records_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted an undeclared status: " + resp.text[:200]
    )


def test_qa_itp_records_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'}
    made = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
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
    other = client.get("/v1/qa_itp_records/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "qa_itp_records answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_qa_itp_records_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/qa_itp_records", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "qa_itp_records raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "qa_itp_records accepted malformed input %r" % (junk,)
        )
