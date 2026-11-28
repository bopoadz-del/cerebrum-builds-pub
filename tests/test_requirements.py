"""Requirement and counter-case tests for the Delivery Service Platform.

Each capability's requirements from the brief are exercised through the real
HTTP routes, and each capability ships at least four counter-cases: a missing
field, a value outside the declared vocabulary, a reserved keyword, and an
unauthenticated request (or a 404 on the placeholder routes).
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import MODELS

AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _sample(capability: str) -> dict:
    model = MODELS[capability]
    payload = {}
    for name in model.FIELDS:
        rules = model.CONSTRAINTS.get(name) or {}
        kind = rules.get("type", "str")
        if rules.get("allowed_values"):
            value = rules["allowed_values"][0]
        elif kind == "int":
            value = 1
        elif kind in ("float", "money", "quantity"):
            value = 1.5
        elif kind == "bool":
            value = False
        elif rules.get("format") == "email":
            value = "guest@example.com"
        elif rules.get("format") == "date":
            value = "2026-09-03"
        elif rules.get("format") == "time":
            value = "10:00:00"
        else:
            value = "sample"
        payload[name] = value
    return payload


def _ref(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex[:10]


def test_customer_booking_flow_requirement_browse_and_book(client):
    for suburb in ("Newtown", "Erskineville"):
        assert client.post("/v1/ops_back_office/suburbs",
                           json={"suburb": suburb, "active": True},
                           headers=AUTH).status_code == 200
    contractor = _ref("contractor")
    onboard = _sample("contractor_onboarding_and_service_areas")
    onboard.update({"reference": contractor, "contractor_name": "River Removals",
                    "service_suburbs": "Newtown, Erskineville", "active": True})
    assert client.post("/v1/contractor_onboarding_and_service_areas", json=onboard, headers=AUTH).status_code == 200

    schedule = _sample("contractor_availability_schedule")
    schedule.update({"reference": _ref("availability"), "contractor_reference": contractor,
                     "weekday": "thursday", "start_time": "08:00:00", "end_time": "17:00:00",
                     "active": True})
    assert client.post("/v1/contractor_availability_schedule", json=schedule, headers=AUTH).status_code == 200

    browse = client.get("/v1/customer_booking_flow/available",
                        params={"suburb": "Newtown", "booking_date": "2026-09-03",
                                "start_time": "09:00:00", "end_time": "10:00:00"},
                        headers=AUTH)
    assert browse.status_code == 200
    refs = [item["contractor_reference"] for item in browse.json()["items"]]
    assert contractor in refs

    booking = _sample("customer_booking_flow")
    booking.update({"reference": _ref("booking"), "contractor_reference": contractor,
                    "suburb": "Newtown", "booking_date": "2026-09-03",
                    "start_time": "09:00:00", "end_time": "10:00:00"})
    created = client.post("/v1/customer_booking_flow", json=booking, headers=AUTH)
    assert created.status_code == 200
    assert created.json()["ok"] is True
    assert created.json()["record"]["suburb"] == "Newtown"


def test_customer_booking_flow_requirement_double_booking_prevented(client):
    contractor = _ref("contractor")
    slot = {"reference": _ref("booking"), "contractor_reference": contractor,
            "suburb": "Newtown", "booking_date": "2026-09-10",
            "start_time": "11:00:00", "end_time": "12:00:00"}
    first = _sample("customer_booking_flow")
    first.update(slot)
    created = client.post("/v1/customer_booking_flow", json=first, headers=AUTH)
    assert created.status_code == 200
    assert created.json()["result"]["slot_state"] == "free"
    # A booking holds its slot from the request, not only after acceptance:
    # a second request for the same contractor and overlapping window is
    # refused as a conflict and stores nothing.
    second = _sample("customer_booking_flow")
    second.update({**slot, "reference": _ref("booking")})
    conflict = client.post("/v1/customer_booking_flow", json=second, headers=AUTH)
    assert conflict.status_code == 409
    assert conflict.json()["error_kind"] == "conflict"
    # Cancelling the first booking (a terminal state) releases the slot.
    lifecycle = _sample("booking_status_lifecycle")
    lifecycle.update({"reference": _ref("transition"), "booking_reference": slot["reference"],
                      "current_state": "requested", "target_state": "cancelled",
                      "actor": "customer"})
    cancelled = client.post("/v1/booking_status_lifecycle", json=lifecycle, headers=AUTH)
    assert cancelled.status_code == 200
    assert cancelled.json()["result"]["allowed"] is True
    third = _sample("customer_booking_flow")
    third.update({**slot, "reference": _ref("booking")})
    rebooked = client.post("/v1/customer_booking_flow", json=third, headers=AUTH)
    assert rebooked.status_code == 200
    assert rebooked.json()["result"]["slot_state"] == "free"


def test_customer_booking_browses_contractors_and_open_slots(client):
    contractor = _ref("contractor")
    onboard = _sample("contractor_onboarding_and_service_areas")
    onboard.update({"reference": contractor, "contractor_name": "Browse Couriers",
                    "service_suburbs": "Marrickville", "active": True})
    assert client.post("/v1/contractor_onboarding_and_service_areas", json=onboard,
                       headers=AUTH).status_code == 200
    schedule = _sample("contractor_availability_schedule")
    schedule.update({"reference": _ref("availability"), "contractor_reference": contractor,
                     "weekday": "thursday", "start_time": "08:00:00", "end_time": "12:00:00",
                     "active": True})
    assert client.post("/v1/contractor_availability_schedule", json=schedule,
                       headers=AUTH).status_code == 200

    booking = _sample("customer_booking_flow")
    booking.update({"reference": _ref("booking"), "contractor_reference": contractor,
                    "suburb": "Marrickville", "booking_date": "2026-09-03",
                    "start_time": "09:00:00", "end_time": "10:00:00"})
    created = client.post("/v1/customer_booking_flow", json=booking, headers=AUTH)
    assert created.status_code == 200
    result = created.json()["result"]
    assert result["verification_state"] == "verified"
    assert result["search"]["total"] >= 1
    browse = [row for row in result["search"]["contractors"]
              if row["contractor_reference"] == contractor]
    assert browse and browse[0]["open_slots"]
    assert any(slot["start"] == "09:00:00" and slot["end"] == "10:00:00"
               for slot in browse[0]["open_slots"])
    assert result["open_slots"]

    listed = client.get("/v1/customer_booking_flow/available",
                        params={"suburb": "Marrickville", "booking_date": "2026-09-03",
                                "start_time": "10:00:00", "end_time": "11:00:00"},
                        headers=AUTH)
    assert listed.status_code == 200
    rows = [row for row in listed.json()["items"]
            if row["contractor_reference"] == contractor]
    assert rows and rows[0]["open_slots"]


def test_customer_booking_refuses_a_confirmed_state_for_an_unregistered_contractor(client):
    booking = _sample("customer_booking_flow")
    booking.update({"reference": _ref("booking"), "contractor_reference": _ref("missing"),
                    "suburb": "Newtown", "booking_date": "2026-09-17",
                    "start_time": "09:00:00", "end_time": "10:00:00",
                    "status": "in_progress"})
    response = client.post("/v1/customer_booking_flow", json=booking, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["rejected_field"] == "contractor_reference"


def test_contractor_onboarding_requirement_accounts_and_suburbs(client):
    # The ops back office maintains the suburb catalogue; onboarding selects
    # from it, so register the two suburbs first.
    for suburb in ("Alexandria", "Zetland"):
        created_suburb = client.post("/v1/ops_back_office/suburbs",
                                     json={"suburb": suburb, "active": True}, headers=AUTH)
        assert created_suburb.status_code == 200, created_suburb.text
    reference = _ref("contractor")
    payload = _sample("contractor_onboarding_and_service_areas")
    payload.update({"reference": reference, "contractor_name": "Harbour Couriers",
                    "service_suburbs": "Alexandria, Zetland", "active": True})
    response = client.post("/v1/contractor_onboarding_and_service_areas", json=payload, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    record = body["record"]
    assert record["reference"] == reference
    assert "Alexandria" in record["service_suburbs"]
    assert body["result"]["activated"] is True
    assert body["result"]["catalogue_size"] >= 2


def test_contractor_onboarding_proposes_an_uncatalogued_suburb(client):
    """The contractor's selection is the service area; ops is asked to catalogue it."""
    reference = _ref("contractor")
    payload = _sample("contractor_onboarding_and_service_areas")
    payload.update({"reference": reference, "contractor_name": "Unlisted Couriers",
                    "service_suburbs": "Nowhereville", "active": True})
    response = client.post("/v1/contractor_onboarding_and_service_areas", json=payload, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["activated"] is True
    assert body["result"]["onboarding_state"] == "active_pending_catalogue"
    assert body["result"]["service_areas"] == ["Nowhereville"]
    assert "Nowhereville" in body["result"]["pending_areas"]
    assert body["record"]["service_suburbs"] == "Nowhereville"

    catalogue = client.get("/v1/ops_back_office/suburbs", headers=AUTH)
    assert catalogue.status_code == 200
    proposals = [item["suburb"] for item in catalogue.json()["proposals"]]
    assert "Nowhereville" in proposals


def test_contractor_onboarding_withholds_a_retired_suburb(client):
    """Only the ops catalogue can retire a suburb; the selection cannot revive it."""
    suburb = "Retired-" + uuid.uuid4().hex[:6]
    created = client.post("/v1/ops_back_office/suburbs",
                          json={"suburb": suburb, "active": False}, headers=AUTH)
    assert created.status_code == 200
    reference = _ref("contractor")
    payload = _sample("contractor_onboarding_and_service_areas")
    payload.update({"reference": reference, "contractor_name": "Retired Couriers",
                    "service_suburbs": suburb, "active": True})
    response = client.post("/v1/contractor_onboarding_and_service_areas", json=payload, headers=AUTH)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["activated"] is False
    assert result["service_areas"] == []
    assert result["retired_areas"] == [suburb]


def test_ops_back_office_maintains_the_suburb_catalogue(client):
    suburb = "Catalogue-" + uuid.uuid4().hex[:6]
    created = client.post("/v1/ops_back_office/suburbs",
                          json={"suburb": suburb, "region": "inner", "active": True},
                          headers=AUTH)
    assert created.status_code == 200
    assert created.json()["record"]["active"] is True
    listed = client.get("/v1/ops_back_office/suburbs", headers=AUTH)
    assert any(row["suburb"] == suburb for row in listed.json()["items"])
    retired = client.post("/v1/ops_back_office/suburbs",
                          json={"suburb": suburb, "active": False}, headers=AUTH)
    assert retired.status_code == 200
    assert retired.json()["record"]["active"] in (False, 0)
    listed = client.get("/v1/ops_back_office/suburbs", headers=AUTH)
    active = [row["suburb"] for row in listed.json()["catalogue"]]
    assert suburb not in active


def test_contractor_availability_requirement_calendar(client):
    payload = _sample("contractor_availability_schedule")
    payload.update({"reference": _ref("availability"), "contractor_reference": _ref("contractor"),
                    "weekday": "friday", "start_time": "09:00:00", "end_time": "12:00:00",
                    "active": True})
    response = client.post("/v1/contractor_availability_schedule", json=payload, headers=AUTH)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["duration_minutes"] == 180
    assert len(result["slots"]) == 3


def test_contractor_availability_treats_reversed_window_as_night_shift(client):
    payload = _sample("contractor_availability_schedule")
    payload.update({"reference": _ref("availability"), "weekday": "monday",
                    "start_time": "22:00:00", "end_time": "06:00:00", "active": True})
    response = client.post("/v1/contractor_availability_schedule", json=payload, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["window"]["crosses_midnight"] is True
    assert body["result"]["duration_minutes"] == 8 * 60
    assert body["result"]["slot_count"] == 8


def test_location_based_matching_requirement_active_suburb(client):
    # A candidate needs an active service area AND a published schedule that
    # covers the requested slot.
    contractor = _ref("contractor")
    suburb = "Match-" + uuid.uuid4().hex[:6]
    onboard = _sample("contractor_onboarding_and_service_areas")
    onboard.update({"reference": contractor, "contractor_name": "Match Couriers",
                    "service_suburbs": suburb, "active": True})
    assert client.post("/v1/contractor_onboarding_and_service_areas", json=onboard,
                       headers=AUTH).status_code == 200
    schedule = _sample("contractor_availability_schedule")
    schedule.update({"reference": _ref("availability"), "contractor_reference": contractor,
                     "weekday": "thursday", "start_time": "08:00:00", "end_time": "17:00:00",
                     "active": True})
    assert client.post("/v1/contractor_availability_schedule", json=schedule,
                       headers=AUTH).status_code == 200

    payload = _sample("location_based_matching")
    payload.update({"reference": _ref("match"), "booking_reference": _ref("booking"),
                    "suburb": suburb, "contractor_reference": contractor,
                    "booking_date": "2026-09-03", "start_time": "09:00:00",
                    "required_skills": "van, lifting"})
    response = client.post("/v1/location_based_matching", json=payload, headers=AUTH)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["matched"] is True
    assert result["ranking"][0]["contractor_reference"] == contractor
    assert result["ranking"][0]["score"] > 0


def test_location_based_matching_excludes_a_contractor_outside_the_schedule(client):
    contractor = _ref("contractor")
    suburb = "Night-" + uuid.uuid4().hex[:6]
    onboard = _sample("contractor_onboarding_and_service_areas")
    onboard.update({"reference": contractor, "contractor_name": "Night Couriers",
                    "service_suburbs": suburb, "active": True})
    assert client.post("/v1/contractor_onboarding_and_service_areas", json=onboard,
                       headers=AUTH).status_code == 200
    schedule = _sample("contractor_availability_schedule")
    schedule.update({"reference": _ref("availability"), "contractor_reference": contractor,
                     "weekday": "thursday", "start_time": "13:00:00", "end_time": "17:00:00",
                     "active": True})
    assert client.post("/v1/contractor_availability_schedule", json=schedule,
                       headers=AUTH).status_code == 200
    payload = _sample("location_based_matching")
    payload.update({"reference": _ref("match"), "booking_reference": _ref("booking"),
                    "suburb": suburb, "contractor_reference": contractor,
                    "booking_date": "2026-09-03", "start_time": "09:00:00"})
    result = client.post("/v1/location_based_matching", json=payload, headers=AUTH).json()["result"]
    assert result["matched"] is False
    assert result["candidates"] == []
    assert [row["contractor_reference"] for row in result["excluded"]] == [contractor]


def test_booking_status_lifecycle_requirement_legal_transition(client):
    payload = _sample("booking_status_lifecycle")
    payload.update({"reference": _ref("lifecycle"), "booking_reference": _ref("booking"),
                    "current_state": "requested", "target_state": "accepted",
                    "actor": "contractor"})
    response = client.post("/v1/booking_status_lifecycle", json=payload, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["result"]["allowed"] is True


def test_booking_status_lifecycle_refuses_illegal_transition(client):
    payload = _sample("booking_status_lifecycle")
    payload.update({"reference": _ref("lifecycle"), "current_state": "requested",
                    "target_state": "completed", "actor": "contractor"})
    response = client.post("/v1/booking_status_lifecycle", json=payload, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["result"]["allowed"] is False


def test_ops_back_office_requirement_dispute_lifecycle(client):
    payload = _sample("ops_back_office")
    payload.update({"reference": _ref("ops"), "dispute_reference": _ref("dispute"),
                    "booking_reference": _ref("booking"), "claimant": "operator",
                    "claim_type": "late_delivery"})
    response = client.post("/v1/ops_back_office", json=payload, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["result"]["state"] == "open"


def test_placeholder_connectors_name_their_settings(client):
    sms = client.post("/v1/booking_notifications", json=_sample("booking_notifications"), headers=AUTH)
    assert sms.status_code == 503
    assert sms.json()["settings"] == ["SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS"]
    money = client.post("/v1/invoicing_and_payouts", json=_sample("invoicing_and_payouts"), headers=AUTH)
    assert money.status_code == 503
    assert len(money.json()["settings"]) == 2


def test_every_capability_round_trips_a_record(client):
    for capability in MODELS:
        if capability in ("booking_notifications", "invoicing_and_payouts"):
            continue
        payload = _sample(capability)
        payload["reference"] = _ref(capability[:12])
        if capability == "customer_booking_flow":
            # Its own unique contractor keeps this out of every other
            # booking test's slot; the capability refuses double-booking.
            payload["contractor_reference"] = payload["reference"]
        created = client.post("/v1/" + capability, json=payload, headers=AUTH)
        assert created.status_code == 200, (capability, created.text[:200])
        assert created.json()["ok"] is True, (capability, created.json())
        record_id = created.json()["id"]
        fetched = client.get("/v1/%s/%s" % (capability, record_id), headers=AUTH)
        assert fetched.status_code == 200
        assert fetched.json()["record"]["reference"] == payload["reference"]


def test_customer_booking_flow_counter_cases(client):
    url = "/v1/customer_booking_flow"
    payload = _sample("customer_booking_flow")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "create"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401
    missing = client.get(url + "/999999", headers=AUTH)
    assert missing.status_code == 404


def test_contractor_onboarding_and_service_areas_counter_cases(client):
    url = "/v1/contractor_onboarding_and_service_areas"
    payload = _sample("contractor_onboarding_and_service_areas")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "register"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_contractor_availability_schedule_counter_cases(client):
    url = "/v1/contractor_availability_schedule"
    payload = _sample("contractor_availability_schedule")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["weekday"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "set"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_location_based_matching_counter_cases(client):
    url = "/v1/location_based_matching"
    payload = _sample("location_based_matching")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "match"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_booking_status_lifecycle_counter_cases(client):
    url = "/v1/booking_status_lifecycle"
    payload = _sample("booking_status_lifecycle")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["target_state"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "transition"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_booking_notifications_counter_cases(client):
    url = "/v1/booking_notifications"
    assert client.post(url, json={}).status_code == 401
    assert client.get(url + "/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/not_a_capability", headers=AUTH).status_code == 404
    assert client.post("/v1/not_a_capability", json={}, headers=AUTH).status_code == 404


def test_invoicing_and_payouts_counter_cases(client):
    url = "/v1/invoicing_and_payouts"
    assert client.post(url, json={}).status_code == 401
    assert client.get(url + "/999999", headers=AUTH).status_code == 404
    assert client.get("/v1/not_a_capability", headers=AUTH).status_code == 404
    assert client.post("/v1/not_a_capability", json={}, headers=AUTH).status_code == 404


def test_ops_back_office_counter_cases(client):
    url = "/v1/ops_back_office"
    payload = _sample("ops_back_office")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "open"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_audit_counter_cases(client):
    url = "/v1/audit"
    payload = _sample("audit")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "log"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_config_counter_cases(client):
    url = "/v1/config"
    payload = _sample("config")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "get"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_email_counter_cases(client):
    url = "/v1/email"
    payload = _sample("email")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "send"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_billing_counter_cases(client):
    url = "/v1/billing"
    payload = _sample("billing")
    assert client.post(url, json={}, headers=AUTH).status_code == 422
    bad = dict(payload); bad["status"] = "__bad__"
    assert client.post(url, json=bad, headers=AUTH).status_code == 422
    reserved = dict(payload); reserved["action"] = "record_usage"
    assert client.post(url, json=reserved, headers=AUTH).status_code == 422
    assert client.post(url, json=payload).status_code == 401


def test_booking_status_lifecycle_actor_guard(client):
    payload = _sample("booking_status_lifecycle")
    payload.update({"reference": _ref("lifecycle"), "current_state": "requested",
                    "target_state": "accepted", "actor": "customer"})
    response = client.post("/v1/booking_status_lifecycle", json=payload, headers=AUTH)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["allowed"] is False
    assert result["decision"] == "actor_not_permitted"


def test_invoicing_reports_currency_withheld_until_declared(monkeypatch):
    from app.actions import invoicing_and_payouts

    monkeypatch.delenv("PLATFORM_CURRENCY", raising=False)
    monkeypatch.delenv("PLATFORM_RATE_PLATFORM_FEE", raising=False)
    out = invoicing_and_payouts.handle({"reference": "invoice-check", "amount": 25.0})
    assert out["ok"] is True
    assert out["result"]["currency"] == "withheld"
    assert out["result"]["currency_setting"] == "PLATFORM_CURRENCY"


def test_ops_back_office_lists_oversight_records(client):
    payload = _sample("ops_back_office")
    payload.update({"reference": _ref("ops"), "dispute_reference": _ref("dispute")})
    assert client.post("/v1/ops_back_office", json=payload, headers=AUTH).status_code == 200
    listed = client.get("/v1/ops_back_office", headers=AUTH)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


def test_booking_notifications_alert_reaches_a_loopback_webhook(monkeypatch):
    """The notification block performs a real outbound POST to the operator's
    configured sink; the capability reports delivered only when it did."""
    import http.server
    import threading

    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            received.append(self.rfile.read(length))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv(
            "NOTIFY_WEBHOOK_URL", "http://127.0.0.1:%d/hook" % server.server_port
        )
        monkeypatch.setenv("NOTIFY_WEBHOOK_ALLOW_PRIVATE", "true")
        from app.actions import booking_notifications

        out = booking_notifications.handle({
            "reference": "alert-1",
            "booking_reference": "booking-9",
            "channel": "webhook",
            "recipient_email": "contractor@example.com",
            "message": "New booking request for Thursday",
            "event_type": "booking_requested",
        })
    finally:
        server.shutdown()
        server.server_close()

    assert out["ok"] is True
    assert out["result"]["audience"] == "contractor"
    assert out["result"]["delivered"] is True
    assert out["result"]["delivery"] == "sent"
    assert received, "no webhook delivery reached the loopback sink"


def test_booking_notifications_keeps_sms_a_declared_placeholder():
    from app.actions import booking_notifications

    out = booking_notifications.handle({
        "reference": "alert-2",
        "booking_reference": "booking-9",
        "channel": "sms",
        "recipient_phone": "+10000000000",
        "message": "New booking",
        "event_type": "booking_requested",
    })
    assert out["ok"] is False
    assert out["error_kind"] == "unavailable"
    assert out["settings"][0].startswith("SMS_GATEWAY_PROVIDER_")


def test_invoicing_runs_hold_release_and_refund(monkeypatch):
    from app.actions import invoicing_and_payouts

    monkeypatch.setenv("PLATFORM_CURRENCY", "USD")
    monkeypatch.setenv("PLATFORM_RATE_PLATFORM_FEE", "0.15")
    monkeypatch.setenv("PLATFORM_TAX_RATE", "0.10")

    hold = invoicing_and_payouts.handle({
        "reference": "invoice-1", "booking_reference": "booking-1",
        "amount": 100.0, "payout_stage": "hold",
    })
    assert hold["ok"] is True
    assert hold["result"]["state"] == "held"
    assert float(hold["result"]["platform_fee"]) == 15.0
    assert hold["result"]["tax"] == 10.0
    assert hold["result"]["authority"]["basis"] == "universal:tax_amount_v1"

    release = invoicing_and_payouts.handle({
        "reference": "invoice-1", "booking_reference": "booking-1",
        "amount": 100.0, "payout_stage": "release",
    })
    assert release["ok"] is True
    assert release["result"]["state"] == "released"

    partial = invoicing_and_payouts.handle({
        "reference": "invoice-1", "booking_reference": "booking-1",
        "amount": 100.0, "payout_stage": "partial_release", "released_amount": 40.0,
    })
    assert partial["ok"] is True
    assert partial["result"]["state"] == "partial"

    refund = invoicing_and_payouts.handle({
        "reference": "invoice-1", "booking_reference": "booking-1",
        "amount": 100.0, "payout_stage": "refund",
    })
    assert refund["ok"] is True
    assert refund["result"]["state"] == "refunded"


def test_invoicing_refuses_a_lifecycle_step_without_a_money_setting(monkeypatch):
    from app.actions import invoicing_and_payouts

    monkeypatch.delenv("PLATFORM_CURRENCY", raising=False)
    monkeypatch.delenv("PLATFORM_RATE_PLATFORM_FEE", raising=False)
    out = invoicing_and_payouts.handle({
        "reference": "invoice-2", "booking_reference": "booking-2",
        "amount": 50.0, "payout_stage": "hold",
    })
    assert out["ok"] is True
    assert out["result"]["state"] == "awaiting_setting"
    assert out["result"]["quote"] == "withheld"
    assert out["result"]["setting"] in {"PLATFORM_CURRENCY", "PLATFORM_RATE_PLATFORM_FEE"}


def test_audit_chain_is_durable_and_verified(client):
    reference = _ref("audit")
    first = _sample("audit")
    first.update({"reference": reference, "event": "booking.created",
                  "resource_type": "booking", "resource_id": reference,
                  "actor": "customer", "notes": "created", "details": "slot 09:00"})
    created = client.post("/v1/audit", json=first, headers=AUTH)
    assert created.status_code == 200
    first_result = created.json()["result"]
    assert first_result["sequence"] >= 1
    assert first_result["chain_digest"]

    second = _sample("audit")
    second.update({"reference": _ref("audit"), "event": "booking.accepted",
                   "resource_type": "booking", "resource_id": reference,
                   "actor": "contractor", "notes": "accepted", "details": "slot 09:00"})
    created = client.post("/v1/audit", json=second, headers=AUTH)
    assert created.status_code == 200
    second_result = created.json()["result"]
    assert second_result["sequence"] == first_result["sequence"] + 1
    assert second_result["previous_digest"] == first_result["chain_digest"]
    assert second_result["chain_verified"] is True
    assert second_result["chain_records_walked"] >= 1

    stored = client.get("/v1/audit/%s" % created.json()["id"], headers=AUTH)
    assert stored.status_code == 200
    assert stored.json()["record"]["chain_digest"] == second_result["chain_digest"]


def test_billing_refuses_a_plan_the_block_does_not_declare(client):
    payload = _sample("billing")
    payload["reference"] = _ref("billing")
    payload["plan"] = "free"
    accepted = client.post("/v1/billing", json=payload, headers=AUTH)
    assert accepted.status_code == 200
    assert accepted.json()["result"]["plan_known"] is True
    assert accepted.json()["result"]["quota_basis"] == "billing.PLANS[free].requests"

    unknown = dict(payload)
    unknown["reference"] = _ref("billing")
    unknown["plan"] = "platinum"
    refused = client.post("/v1/billing", json=unknown, headers=AUTH)
    assert refused.status_code == 422
    assert refused.json()["rejected_field"] == "plan"


def test_contractor_availability_labels_improvised_slot_algebra(client):
    payload = _sample("contractor_availability_schedule")
    payload.update({"reference": _ref("availability"), "contractor_reference": _ref("contractor"),
                    "weekday": "tuesday", "start_time": "09:00:00", "end_time": "12:00:00",
                    "active": True})
    response = client.post("/v1/contractor_availability_schedule", json=payload, headers=AUTH)
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["authority"]["label"] == "improvised, no Store coverage"
    assert "delivery:slot_count_v1" in result["formula_sources"]
    assert result["slot_count"] == 3

def test_contractor_onboarding_updates_an_existing_profile(client):
    reference = _ref("contractor")
    first = _sample("contractor_onboarding_and_service_areas")
    first.update({"reference": reference, "contractor_name": "Harbour Couriers",
                  "service_suburbs": "Alexandria", "active": True})
    created = client.post("/v1/contractor_onboarding_and_service_areas", json=first, headers=AUTH)
    assert created.status_code == 200
    record_id = created.json()["id"]
    second = dict(first)
    second.update({"contractor_name": "Harbour Couriers Pty",
                   "service_suburbs": "Alexandria, Zetland"})
    updated = client.post("/v1/contractor_onboarding_and_service_areas", json=second, headers=AUTH)
    assert updated.status_code == 200
    assert updated.json()["id"] == record_id
    assert updated.json()["record"]["contractor_name"] == "Harbour Couriers Pty"
    assert set(updated.json()["result"]["service_areas"]) == {"Alexandria", "Zetland"}


def test_onboarding_counts_and_channels_are_grounded_in_the_payload(client):
    reference = _ref("contractor")
    payload = _sample("contractor_onboarding_and_service_areas")
    payload.update({"reference": reference, "contractor_name": "Grounded Couriers",
                    "service_suburbs": "Alexandria, Zetland, Nowhereville",
                    "contact_email": "grounded@example.com", "phone": "", "active": True})
    result = client.post("/v1/contractor_onboarding_and_service_areas",
                         json=payload, headers=AUTH).json()["result"]
    assert result["contact_channels"] == ["email"]
    assert result["contact_channel_count"] == 1
    assert result["service_area_count"] == 3
    assert result["pending_area_count"] == 1
    assert result["authority"]["label"] == "procedure"
    assert result["claims"]["contact_channel_count"]["value"] == 1
    assert result["claims"]["vendor_id"]["authority"]["label"] == "certified"


def test_availability_numbers_carry_their_source(client):
    payload = _sample("contractor_availability_schedule")
    payload.update({"reference": _ref("availability"), "contractor_reference": _ref("contractor"),
                    "weekday": "friday", "start_time": "09:00:00", "end_time": "12:00:00",
                    "active": True})
    result = client.post("/v1/contractor_availability_schedule",
                         json=payload, headers=AUTH).json()["result"]
    assert result["claims"]["slot_count"]["value"] == 3
    assert result["claims"]["slot_count"]["authority"]["label"] == "improvised, no Store coverage"
    assert result["claims"]["duration_minutes"]["authority"]["layer"] == 4
    assert result["authority"]["basis"] == "delivery:slot_count_v1"

