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



# -- claims_analytics_dashboard ----------------------------------


def test_claims_analytics_dashboard_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1}
    resp = client.post("/v1/claims_analytics_dashboard", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "claims_analytics_dashboard accepted a payload with no reference: " + resp.text[:200]
    )


def test_claims_analytics_dashboard_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1}
    resp = client.post("/v1/claims_analytics_dashboard", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "claims_analytics_dashboard accepted an undeclared status: " + resp.text[:200]
    )


def test_claims_analytics_dashboard_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1}
    made = client.post("/v1/claims_analytics_dashboard", json=body, headers=AUTH)
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
    other = client.get("/v1/claims_analytics_dashboard/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "claims_analytics_dashboard answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_claims_analytics_dashboard_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/claims_analytics_dashboard", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "claims_analytics_dashboard raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "claims_analytics_dashboard accepted malformed input %r" % (junk,)
        )


# -- contract_clause_governance ----------------------------------


def test_contract_clause_governance_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'}
    resp = client.post("/v1/contract_clause_governance", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "contract_clause_governance accepted a payload with no reference: " + resp.text[:200]
    )


def test_contract_clause_governance_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'}
    resp = client.post("/v1/contract_clause_governance", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "contract_clause_governance accepted an undeclared status: " + resp.text[:200]
    )


def test_contract_clause_governance_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'}
    made = client.post("/v1/contract_clause_governance", json=body, headers=AUTH)
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
    other = client.get("/v1/contract_clause_governance/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "contract_clause_governance answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_contract_clause_governance_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/contract_clause_governance", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "contract_clause_governance raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "contract_clause_governance accepted malformed input %r" % (junk,)
        )


# -- delay_damages_tracking --------------------------------------


def test_delay_damages_tracking_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0}
    resp = client.post("/v1/delay_damages_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "delay_damages_tracking accepted a payload with no reference: " + resp.text[:200]
    )


def test_delay_damages_tracking_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0}
    resp = client.post("/v1/delay_damages_tracking", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "delay_damages_tracking accepted an undeclared status: " + resp.text[:200]
    )


def test_delay_damages_tracking_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0}
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
    body = {'status': 'open', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted a payload with no reference: " + resp.text[:200]
    )


def test_document_register_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted an undeclared status: " + resp.text[:200]
    )


def test_document_register_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'}
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


# -- payment_security_and_retention_ledger -----------------------


def test_payment_security_and_retention_ledger_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'}
    resp = client.post("/v1/payment_security_and_retention_ledger", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "payment_security_and_retention_ledger accepted a payload with no reference: " + resp.text[:200]
    )


def test_payment_security_and_retention_ledger_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'}
    resp = client.post("/v1/payment_security_and_retention_ledger", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "payment_security_and_retention_ledger accepted an undeclared status: " + resp.text[:200]
    )


def test_payment_security_and_retention_ledger_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'}
    made = client.post("/v1/payment_security_and_retention_ledger", json=body, headers=AUTH)
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
    other = client.get("/v1/payment_security_and_retention_ledger/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "payment_security_and_retention_ledger answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_payment_security_and_retention_ledger_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/payment_security_and_retention_ledger", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "payment_security_and_retention_ledger raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "payment_security_and_retention_ledger accepted malformed input %r" % (junk,)
        )


# -- progress_claims ---------------------------------------------


def test_progress_claims_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'}
    resp = client.post("/v1/progress_claims", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claims accepted a payload with no reference: " + resp.text[:200]
    )


def test_progress_claims_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'}
    resp = client.post("/v1/progress_claims", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claims accepted an undeclared status: " + resp.text[:200]
    )


def test_progress_claims_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'}
    made = client.post("/v1/progress_claims", json=body, headers=AUTH)
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
    other = client.get("/v1/progress_claims/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "progress_claims answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_progress_claims_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/progress_claims", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "progress_claims raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "progress_claims accepted malformed input %r" % (junk,)
        )


# -- qa_itp_records ----------------------------------------------


def test_qa_itp_records_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'status': 'open', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted a payload with no reference: " + resp.text[:200]
    )


def test_qa_itp_records_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'status': 'not-a-declared-value', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted an undeclared status: " + resp.text[:200]
    )


def test_qa_itp_records_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'status': 'open', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'}
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
