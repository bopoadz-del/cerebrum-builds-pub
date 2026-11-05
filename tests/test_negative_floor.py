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



# -- contract_source_of_record -----------------------------------


def test_contract_source_of_record_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'source_document': 'document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'}
    resp = client.post("/v1/contract_source_of_record", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "contract_source_of_record accepted a payload with no reference: " + resp.text[:200]
    )


def test_contract_source_of_record_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'source_document': 'not-a-declared-value', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'}
    resp = client.post("/v1/contract_source_of_record", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "contract_source_of_record accepted an undeclared source_document: " + resp.text[:200]
    )


def test_contract_source_of_record_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'source_document': 'document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'}
    made = client.post("/v1/contract_source_of_record", json=body, headers=AUTH)
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
    other = client.get("/v1/contract_source_of_record/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "contract_source_of_record answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_contract_source_of_record_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/contract_source_of_record", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "contract_source_of_record raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "contract_source_of_record accepted malformed input %r" % (junk,)
        )


# -- document_register -------------------------------------------


def test_document_register_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted a payload with no reference: " + resp.text[:200]
    )


def test_document_register_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'title': 'sample', 'document_type': 'not-a-declared-value', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'}
    resp = client.post("/v1/document_register", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "document_register accepted an undeclared document_type: " + resp.text[:200]
    )


def test_document_register_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'}
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


# -- progress_claims ---------------------------------------------


def test_progress_claims_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'ipc_number': 'sample', 'boq_item': 'P1', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'}
    resp = client.post("/v1/progress_claims", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claims accepted a payload with no reference: " + resp.text[:200]
    )


def test_progress_claims_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'ipc_number': 'sample', 'boq_item': 'not-a-declared-value', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'}
    resp = client.post("/v1/progress_claims", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "progress_claims accepted an undeclared boq_item: " + resp.text[:200]
    )


def test_progress_claims_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'ipc_number': 'sample', 'boq_item': 'P1', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'}
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
    body = {'boq_item': 'P1', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted a payload with no reference: " + resp.text[:200]
    )


def test_qa_itp_records_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'boq_item': 'not-a-declared-value', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'}
    resp = client.post("/v1/qa_itp_records", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "qa_itp_records accepted an undeclared boq_item: " + resp.text[:200]
    )


def test_qa_itp_records_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'boq_item': 'P1', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'}
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


# -- role_based_access_and_audit ---------------------------------


def test_role_based_access_and_audit_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'principal_id': 'sample', 'role': 'owner', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'}
    resp = client.post("/v1/role_based_access_and_audit", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "role_based_access_and_audit accepted a payload with no reference: " + resp.text[:200]
    )


def test_role_based_access_and_audit_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'principal_id': 'sample', 'role': 'not-a-declared-value', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'}
    resp = client.post("/v1/role_based_access_and_audit", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "role_based_access_and_audit accepted an undeclared role: " + resp.text[:200]
    )


def test_role_based_access_and_audit_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'principal_id': 'sample', 'role': 'owner', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'}
    made = client.post("/v1/role_based_access_and_audit", json=body, headers=AUTH)
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
    other = client.get("/v1/role_based_access_and_audit/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "role_based_access_and_audit answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_role_based_access_and_audit_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/role_based_access_and_audit", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "role_based_access_and_audit raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "role_based_access_and_audit accepted malformed input %r" % (junk,)
        )


# -- time_and_delay_damages --------------------------------------


def test_time_and_delay_damages_refuses_a_missing_required_field():
    """A partial record is refused, never completed by the handler."""
    body = {'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'open'}
    resp = client.post("/v1/time_and_delay_damages", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "time_and_delay_damages accepted a payload with no reference: " + resp.text[:200]
    )


def test_time_and_delay_damages_refuses_a_value_outside_its_vocabulary():
    """A column that accepts any string is not that column."""
    body = {'reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'not-a-declared-value'}
    resp = client.post("/v1/time_and_delay_damages", json=body, headers=AUTH)
    assert resp.status_code in REFUSED or _refused(resp), (
        "time_and_delay_damages accepted an undeclared status: " + resp.text[:200]
    )


def test_time_and_delay_damages_does_not_leak_across_tenants():
    """404, never 403 and never the row: existence itself is private."""
    body = {'reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'open'}
    made = client.post("/v1/time_and_delay_damages", json=body, headers=AUTH)
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
    other = client.get("/v1/time_and_delay_damages/" + str(rid), headers=OTHER_TENANT)
    assert other.status_code == CROSS_TENANT_READ, (
        "time_and_delay_damages answered %s to another tenant, not %s" % (other.status_code, CROSS_TENANT_READ)
    )


def test_time_and_delay_damages_refuses_a_malformed_payload():
    """Garbage in is a refusal, never a 500 and never a stored row."""
    for junk in ([], "", {"": None}, {"x" * 300: "y" * 2000}):
        resp = client.post("/v1/time_and_delay_damages", json=junk, headers=AUTH)
        assert resp.status_code != 500, (
            "time_and_delay_damages raised on malformed input: " + resp.text[:200]
        )
        assert resp.status_code in REFUSED or _refused(resp), (
            "time_and_delay_damages accepted malformed input %r" % (junk,)
        )
