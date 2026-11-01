"""The six capabilities, exercised the way the factory will exercise them.

Each capability accepts a payload built from its own declared model, returns
its decision (ok, record id), and the record is readable back from the
capability route. Invoice arithmetic is asserted with the customer's VAT rate.
"""

from __future__ import annotations

import typing

import pytest

from app.models import MODELS

AUTH = {"Authorization": "Bearer dev-local-token"}


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


@pytest.mark.parametrize("capability_id", sorted(MODELS))
def test_each_capability_accepts_and_remembers_a_record(client, capability_id):
    payload = sample_payload(capability_id, reference="rt-" + capability_id)
    created = client.post("/v1/" + capability_id, json=payload, headers=AUTH)
    assert created.status_code == 200, created.text[:300]
    body = created.json()
    assert body.get("ok") is not False, body.get("error")
    assert isinstance(body.get("id"), int)
    assert body["stored"]["reference"] == "rt-" + capability_id

    fetched = client.get("/v1/%s/%s" % (capability_id, body["id"]), headers=AUTH)
    assert fetched.status_code == 200
    assert fetched.json()["reference"] == "rt-" + capability_id

    listed = client.get("/v1/" + capability_id + "?limit=200", headers=AUTH)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["items"]}
    assert body["id"] in ids


def test_invoice_applies_the_customer_vat_rate(client, monkeypatch):
    monkeypatch.setenv("PLATFORM_TAX_RATE", "0.19")
    payload = sample_payload(
        "invoicing_tunisian_vat",
        quantity=2,
        unit_price_ht=100,
        vat_exempt=False,
        reference="inv-vat",
    )
    resp = client.post("/v1/invoicing_tunisian_vat", json=payload, headers=AUTH)
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    assert body.get("ok") is not False, body.get("error")
    decision = body["result"]
    assert decision["net_total"] == 200.0
    assert decision["vat_rate"] == 0.19
    assert decision["vat_amount"] == 38.0
    assert decision["gross_total"] == 238.0
    assert decision["currency"] == "TND"
    assert decision["compliance"]["compliant"] is True


def test_invoice_exemption_applies_no_vat(client):
    payload = sample_payload(
        "invoicing_tunisian_vat",
        quantity=1, unit_price_ht=100, vat_exempt=True, reference="inv-exempt",
    )
    resp = client.post("/v1/invoicing_tunisian_vat", json=payload, headers=AUTH)
    assert resp.status_code == 200
    decision = resp.json()["result"]
    assert decision["vat_rate"] == 0.0
    assert decision["vat_amount"] == 0.0
    assert decision["gross_total"] == 100.0


def test_collection_shortfall_is_computed_against_the_plan(client):
    payload = sample_payload(
        "collection_planning_tracking",
        planned_kg=100, collected_kg=80, reference="pick-short",
    )
    resp = client.post("/v1/collection_planning_tracking", json=payload, headers=AUTH)
    assert resp.status_code == 200
    decision = resp.json()["result"]
    assert decision["shortfall"]["shortfall_pct"] == 20.0
    assert decision["shortfall"]["alert"] is True
    assert "chase_source" in decision["actions_due"]


def test_batch_quality_reading_and_next_action(client):
    payload = sample_payload(
        "batch_production_tracking",
        stage="curing", curing_days=45, quality_result="pass",
        temperature_c=35, moisture_pct=50, ph=7.0, c_n_ratio=25,
        reference="batch-q",
    )
    resp = client.post("/v1/batch_production_tracking", json=payload, headers=AUTH)
    assert resp.status_code == 200
    decision = resp.json()["result"]
    assert decision["curing"]["progress_pct"] == 100.0
    assert decision["quality"]["verdict"] == "pass"


def test_order_line_total_uses_declared_quantity_and_price(client):
    payload = sample_payload(
        "catalog_pricing_orders",
        quantity=3, unit_price=12.5, discount_pct=10, reference="order-total",
    )
    resp = client.post("/v1/catalog_pricing_orders", json=payload, headers=AUTH)
    assert resp.status_code == 200
    decision = resp.json()["result"]
    pricing = decision["pricing"]
    assert pricing["gross_line"] == 37.5
    assert pricing["discount_amount"] == 3.75
    assert pricing["net_total"] == 33.75


AUTH_B = {"Authorization": "Bearer dev-local-token-b"}


def _reading(client, headers=AUTH, **fields):
    payload = {"reference": "dash-" + str(fields.get("reference", "reading")), "status": "open"}
    payload.update(fields)
    resp = client.post("/v1/operational_dashboard", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text[:300]
    body = resp.json()
    assert body.get("ok") is not False, body.get("error")
    return body["result"]


def _create(client, capability_id, headers=AUTH, **fields):
    payload = sample_payload(capability_id, **fields)
    resp = client.post("/v1/" + capability_id, json=payload, headers=headers)
    assert resp.status_code == 200, resp.text[:300]
    assert resp.json().get("ok") is not False, resp.json().get("error")


def test_dashboard_measures_the_tenants_own_records(client):
    """The reading is taken from the platform's rows, not typed by the caller."""
    before = _reading(client)
    _create(client, "collection_planning_tracking", reference="agg-open", status="open")
    _create(client, "collection_planning_tracking", reference="agg-closed", status="closed")
    _create(
        client, "batch_production_tracking", reference="agg-curing",
        status="in_progress", stage="curing", quality_result="fail",
    )
    _create(client, "catalog_pricing_orders", reference="agg-order", status="open")
    _create(
        client, "invoicing_tunisian_vat", reference="agg-invoice",
        status="open", payment_state="unpaid",
    )
    _create(
        client, "invoicing_tunisian_vat", reference="agg-paid",
        status="closed", payment_state="paid", quantity=2, unit_price_ht=100,
    )
    after = _reading(client)

    assert after["collections_open"] == before["collections_open"] + 1
    assert after["batches_in_curing"] == before["batches_in_curing"] + 1
    assert after["orders_open"] == before["orders_open"] + 1
    assert after["invoices_unpaid"] == before["invoices_unpaid"] + 1
    assert after["quality_failures"] == before["quality_failures"] + 1
    assert after["revenue_total"] == before["revenue_total"] + 200.0
    assert after["open_queues"]["collections"] == after["collections_open"]
    assert after["busiest_queue_open"] == max(after["open_queues"].values())
    assert "completion_pct" not in after

    typed = _reading(client, collections_open=999)
    assert typed["collections_open"] == after["collections_open"]


def test_dashboard_is_scoped_to_the_callers_tenant(client):
    """Another tenant's rows are invisible: the reading is that tenant's own."""
    before = _reading(client, headers=AUTH_B, reference="tenant-b-before")
    _create(
        client, "collection_planning_tracking", reference="scoped-a",
        status="open",
    )
    after = _reading(client, headers=AUTH_B, reference="tenant-b-after")
    for field in ("collections_open", "batches_in_curing", "orders_open",
                  "invoices_unpaid", "quality_failures", "work_in_progress"):
        assert after[field] == before[field], field
    assert after["busiest_queue"] == before["busiest_queue"]
