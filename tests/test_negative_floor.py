"""Counter-cases: the platform refuses what the brief says is wrong.

Per capability: an invalid vocabulary value, a cross-tenant read, a rule
boundary exercised exactly on the line (and just past it), and a malformed
payload. A refusal is a 4xx or ``ok: false``, never a 500.
"""

from __future__ import annotations

import typing

import pytest

from app.models import MODELS

TOKEN_A = "dev-local-token"
TOKEN_B = "dev-local-token-b"
AUTH_A = {"Authorization": "Bearer " + TOKEN_A}
AUTH_B = {"Authorization": "Bearer " + TOKEN_B}


def sample_payload(capability_id: str, **overrides):
    cls = MODELS[capability_id]
    hints = typing.get_type_hints(cls)
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    payload = {}
    for name in cls.FIELDS:
        rule = constraints.get(name) or {}
        allowed = rule.get("allowed_values")
        fmt = str(rule.get("format") or "")
        kind = hints.get(name, str)
        if allowed:
            value = allowed[0]
        elif fmt == "date":
            value = "2026-09-03"
        elif fmt == "datetime":
            value = "2026-09-03T10:00:00"
        elif fmt == "email":
            value = "guest@example.com"
        elif kind is bool:
            value = False
        elif kind is int:
            value = int(rule.get("min") or 0)
        elif kind is float:
            value = float(rule.get("min") or 0.0)
        else:
            value = "sample"
        payload[name] = value
    payload.update(overrides)
    return payload


def _refused(resp):
    if resp.status_code >= 500:
        return False
    if resp.status_code >= 400:
        return True
    body = resp.json()
    return isinstance(body, dict) and body.get("ok") is False


def _create(client, cap, **overrides):
    return client.post("/v1/" + cap, json=sample_payload(cap, **overrides), headers=AUTH_A)


ALL_CAPS = sorted(MODELS)


@pytest.mark.parametrize("capability_id", ALL_CAPS)
def test_invalid_vocabulary_is_refused(client, capability_id):
    """`status` is exactly open|in_progress|closed; anything else is 422."""
    resp = _create(client, capability_id, status="archived")
    assert _refused(resp), (capability_id, resp.status_code, resp.text[:300])


@pytest.mark.parametrize("capability_id", ALL_CAPS)
def test_cross_tenant_record_is_invisible(client, capability_id):
    """Tenant B never sees tenant A's record: GET is 404, the list omits it."""
    created = _create(client, capability_id)
    assert created.status_code == 200 and created.json().get("ok") is not False, created.text[:300]
    item_id = created.json()["id"]
    fetched = client.get("/v1/%s/%s" % (capability_id, item_id), headers=AUTH_B)
    assert fetched.status_code == 404, (capability_id, fetched.status_code)
    listed = client.get("/v1/" + capability_id + "?limit=200", headers=AUTH_B)
    assert listed.status_code == 200
    ids = {row.get("id") for row in listed.json().get("items", [])}
    assert item_id not in ids, capability_id


@pytest.mark.parametrize("capability_id", ALL_CAPS)
def test_malformed_payload_is_refused_not_500(client, capability_id):
    """A field of the wrong JSON type is a 422, never a server error."""
    resp = client.post(
        "/v1/" + capability_id,
        json={"reference": ["not", "text"], "status": "open"},
        headers=AUTH_A,
    )
    assert resp.status_code == 422, (capability_id, resp.status_code, resp.text[:200])
    not_an_object = client.post("/v1/" + capability_id, json=["fuzz"], headers=AUTH_A)
    assert not_an_object.status_code == 422, (capability_id, not_an_object.status_code)


def test_collection_zero_plan_boundary(client):
    """A zero planned weight is a valid boundary: 0% shortfall, nothing chased."""
    resp = _create(client, "collection_planning_tracking", planned_kg=0.0, collected_kg=0.0)
    assert resp.status_code == 200 and resp.json().get("ok") is not False
    decision = resp.json()["result"]
    assert decision["shortfall"]["shortfall_pct"] == 0.0
    assert decision["shortfall"]["alert"] is False
    below = _create(client, "collection_planning_tracking", planned_kg=-1)
    assert _refused(below)


def test_batch_ph_boundary(client):
    """pH is declared 3..10: exactly 3 is accepted, 2.99 is refused."""
    on_line = _create(client, "batch_production_tracking", ph=3.0)
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False
    past = _create(client, "batch_production_tracking", ph=2.99)
    assert _refused(past)


def test_catalog_discount_boundary(client):
    """Discount is declared 0..100: exactly 100 is accepted, 100.1 is refused."""
    on_line = _create(client, "catalog_pricing_orders", discount_pct=100)
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False
    past = _create(client, "catalog_pricing_orders", discount_pct=100.1)
    assert _refused(past)


def test_invoice_vat_rate_boundary(client, monkeypatch):
    """The invoice's own rate is 0..1: exactly 1 is accepted, 1.01 is refused.

    No PLATFORM_TAX_RATE is set here, so the handler states it used the invoice
    field rather than inventing a rate.
    """
    monkeypatch.delenv("PLATFORM_TAX_RATE", raising=False)
    on_line = _create(client, "invoicing_tunisian_vat", vat_rate=1.0, quantity=1, unit_price_ht=100)
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False, on_line.text[:300]
    assert on_line.json()["result"]["vat_rate"] == 1.0
    assert on_line.json()["result"]["vat_amount"] == 100.0
    assert on_line.json()["result"]["gross_total"] == 200.0
    past = _create(client, "invoicing_tunisian_vat", vat_rate=1.01)
    assert _refused(past)


def test_invoice_due_date_cannot_precede_issue_date(client):
    """The invoice's timeline is declared, not assumed.

    A payment due the day the invoice is issued is the boundary and is
    accepted; one day earlier is refused 422 naming the field. The rule is
    enforced from the field's own ``not_before`` declaration, so it holds for
    any capability that declares a timeline.
    """
    on_line = _create(
        client, "invoicing_tunisian_vat",
        invoice_date="2026-09-03", due_date="2026-09-03",
    )
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False, on_line.text[:300]
    past = _create(
        client, "invoicing_tunisian_vat",
        invoice_date="2026-09-03", due_date="2026-09-02",
    )
    assert past.status_code == 422, past.text[:200]
    assert "due_date" in past.json().get("detail", "")
    unreadable = _create(
        client, "invoicing_tunisian_vat",
        invoice_date="2026-09-03", due_date="next tuesday",
    )
    assert unreadable.status_code == 422, unreadable.text[:200]


def test_collection_delivery_cannot_precede_pickup(client):
    """A truck cannot deliver a pickup before the pickup happened.

    The delivery is a datetime and the pickup a date: the date is its
    midnight, so a same-day delivery at midnight is the boundary and is
    accepted, while one second before it is refused.
    """
    on_line = _create(
        client, "collection_planning_tracking",
        pickup_date="2026-09-03", delivered_on="2026-09-03T00:00:00",
    )
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False, on_line.text[:300]
    earlier = _create(
        client, "collection_planning_tracking",
        pickup_date="2026-09-03", delivered_on="2026-09-02T23:59:59",
    )
    assert earlier.status_code == 422, earlier.text[:200]


def test_staff_revocation_needs_a_known_approver(client):
    """Revoking access is an approval act: free text is refused, a known
    principal is accepted, and the handler records the revocation."""
    free_text = _create(
        client, "internal_staff_access",
        access_state="revoked", approved_by="i am the director trust me",
    )
    assert free_text.status_code == 403, free_text.text[:200]
    known = _create(
        client, "internal_staff_access",
        access_state="revoked", approved_by="director-jane",
    )
    assert known.status_code == 200 and known.json().get("ok") is not False, known.text[:300]
    assert known.json()["result"]["access_granted"] is False


def test_dashboard_zero_count_boundary(client):
    """Operational counts are declared >= 0: 0 is accepted, -1 is refused.

    The posted number is validated at the edge even though the reading the
    capability answers with is MEASURED from the tenant's own rows (a
    dashboard count is not typed in): the boundary is on the caller's
    payload, and -1 is refused before any reading is taken.
    """
    on_line = _create(
        client, "operational_dashboard",
        collections_open=0, batches_in_curing=0, orders_open=0,
        invoices_unpaid=0, quality_failures=0, revenue_total=0,
    )
    assert on_line.status_code == 200 and on_line.json().get("ok") is not False
    measured = on_line.json()["result"]
    assert isinstance(measured["work_in_progress"], int)
    assert measured["work_in_progress"] >= 0
    past = _create(client, "operational_dashboard", collections_open=-1)
    assert _refused(past)


@pytest.mark.parametrize("path", [
    "/v1/jobs",
    "/v1/capabilities",
    "/v1/collection_planning_tracking",
    "/v1/operational_dashboard",
])
def test_v1_routes_require_a_token(client, path):
    """No bearer token is 401, not an anonymous read of the platform tenant."""
    assert client.get(path).status_code == 401


def test_put_cannot_erase_an_approved_revocation(client):
    """A PUT replaces the record, never the columns it forgot to name.

    Writing only the supplied keys used to NULL access_state/approved_by, so
    a revoked principal came back as invited and the name of the approver who
    revoked them was destroyed — the platform's one approval control, undone
    by a required-fields-only update.
    """
    created = _create(
        client, "internal_staff_access",
        reference="revoke-put", status="open",
        principal_id="put-1", principal_name="Put One", role="finance",
        access_state="revoked", approved_by="director-jane",
    )
    assert created.status_code == 200 and created.json().get("ok") is not False
    record_id = created.json()["id"]
    minimal = {
        "reference": "revoke-put", "status": "open",
        "principal_id": "put-1", "principal_name": "Put One", "role": "finance",
    }
    updated = client.put(
        "/v1/internal_staff_access/%d" % record_id, json=minimal, headers=AUTH_A
    )
    assert updated.status_code == 200, updated.text[:300]
    body = updated.json()
    assert body.get("ok") is not False, body.get("error")
    assert body["stored"]["access_state"] == "revoked"
    assert body["stored"]["approved_by"] == "director-jane"
    assert body["result"]["access_granted"] is False


def test_put_cannot_self_approve_a_revocation(client):
    """The approval is judged on the resulting record, not on a new payload."""
    created = _create(
        client, "internal_staff_access",
        reference="revoke-put-2", status="open",
        principal_id="put-2", principal_name="Put Two", role="finance",
        access_state="revoked", approved_by="director-jane",
    )
    record_id = created.json()["id"]
    forged = {
        "reference": "revoke-put-2", "status": "open",
        "principal_id": "put-2", "principal_name": "Put Two", "role": "finance",
        "approved_by": "i am the director trust me",
    }
    updated = client.put(
        "/v1/internal_staff_access/%d" % record_id, json=forged, headers=AUTH_A
    )
    assert updated.status_code == 403, updated.text[:300]


@pytest.mark.parametrize("literal", ["Infinity", "-Infinity", "NaN"])
def test_non_finite_numbers_are_refused(client, literal):
    """NaN/Infinity parse as JSON in Python and defeat every min/max bound.

    The body is sent as raw JSON on purpose: a compliant client refuses to
    encode these literals, and the attack is the non-compliant one.
    """
    body = (
        '{"reference": "nonfinite", "status": "open", '
        '"invoice_number": "NF-1", "customer_name": "Cafe", '
        '"quantity": %s, "unit_price_ht": 10}' % literal
    )
    resp = client.post(
        "/v1/invoicing_tunisian_vat",
        content=body,
        headers={**AUTH_A, "Content-Type": "application/json"},
    )
    assert resp.status_code == 422, resp.text[:300]


def test_unknown_and_non_ascii_tokens_are_refused(client):
    """An unbound token is 401, whatever bytes it carries.

    The token comparison is constant time and compares bytes, so a token
    outside ASCII is refused as unbound rather than raising inside the
    comparison and answering 500.
    """
    for token in ("not-a-token",):
        resp = client.get(
            "/v1/capabilities", headers={"Authorization": "Bearer " + token}
        )
        assert resp.status_code == 401, (token, resp.status_code)
    # Raw bytes, not str: an HTTP client refuses to ASCII-encode a header the
    # platform must still answer as a refusal. Starlette decodes the header as
    # latin-1, so the product sees a non-ASCII token it has never bound.
    raw = client.get("/v1/capabilities", headers={"Authorization": b"Bearer tok\xff"})
    assert raw.status_code == 401, raw.status_code
