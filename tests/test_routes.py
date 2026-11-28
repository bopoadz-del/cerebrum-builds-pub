"""The HTTP surface answers, and what it answers has the right shape."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {'Authorization': 'Bearer ' + __import__('os').environ.get('PLATFORM_TOKEN', 'dev-local-token')}


def _listed(payload):
    """The records a list route answered -- by shape, never a guessed key."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict) or payload.get('ok') is False:
        return []
    out = []
    for value in payload.values():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            out.extend(value)
    return out


import dataclasses as _dataclasses
import json as _json

_SAMPLE_BY_TYPE = {'str': 'sample', 'int': 1, 'float': 1.5, 'bool': True}
_ACCEPT_STATUSES = (200,)
_OK_KEY = 'ok'


def _model_of(capability_id):
    try:
        from app.models import MODELS
    except Exception:
        return None
    return MODELS.get(capability_id)


def _field_sample(capability_id, field):
    """A value the product's own model declares acceptable for ``field``."""
    cls = _model_of(capability_id)
    if cls is None:
        return None
    rules = (getattr(cls, 'CONSTRAINTS', {}) or {}).get(field) or {}
    allowed = rules.get('allowed_values')
    if allowed:
        return allowed[0]
    default = None
    if _dataclasses.is_dataclass(cls):
        attr = (getattr(cls, '_FIELD_PY', {}) or {}).get(field, field)
        for f in _dataclasses.fields(cls):
            if f.name != attr:
                continue
            if f.default is not _dataclasses.MISSING:
                default = f.default
            elif f.default_factory is not _dataclasses.MISSING:
                default = f.default_factory()
    low = rules.get('min')
    if default not in (None, '') and not isinstance(default, bool):
        if not isinstance(default, (int, float)) or default:
            if low is None or not isinstance(default, (int, float)) or default >= low:
                return default
    sample = _SAMPLE_BY_TYPE.get(type(default).__name__, _SAMPLE_BY_TYPE['str'])
    if low is not None and isinstance(sample, (int, float)) and sample < low:
        sample = low
    return sample


def _sample_payload_for(capability_id, base):
    """The Factory spec sample, completed with every field the product's
    own model declares required and the sample lacks."""
    payload = dict(base or {})
    cls = _model_of(capability_id)
    if cls is None:
        return payload
    constraints = getattr(cls, 'CONSTRAINTS', {}) or {}
    for name in list(getattr(cls, 'FIELDS', []) or []):
        if not (constraints.get(name) or {}).get('required'):
            continue
        if payload.get(name) in (None, ''):
            value = _field_sample(capability_id, name)
            if value not in (None, ''):
                payload[name] = value
    return payload


def _rejection(resp):
    """The rejection as data: (field, reason, allowed) or None. Read from
    the structured rejection the product states -- headers on a 422,
    keys on an ok:false body -- never from prose or JSON text, so no
    token in a response body can leak into a payload."""
    field = resp.headers.get('X-Rejected-Field')
    if field is not None:
        try:
            field = _json.loads(field)
        except ValueError:
            return None
        reason = resp.headers.get('X-Rejection-Reason')
        allowed = resp.headers.get('X-Allowed-Values')
        try:
            allowed = _json.loads(allowed) if allowed is not None else None
        except ValueError:
            allowed = None
        return field, reason, allowed
    try:
        body = resp.json()
    except Exception:
        return None
    return _body_rejection(body)


def _body_rejection(body):
    """The rejection an ok:false body states as keys: (field, reason,
    allowed), or None when the body names no rejected field."""
    if not isinstance(body, dict) or 'rejected_field' not in body:
        return None
    return (body.get('rejected_field'), body.get('rejection_reason'),
            body.get('allowed_values'))


def _corrected(rejection, capability_id, tried):
    """The correction a stated rejection names: (field, value) -- the
    first allowed value for NOT_ALLOWED, the product's own model sample
    for MISSING_REQUIRED -- or None when it names none or the same
    (field, value) was already tried (``tried`` is updated)."""
    field, reason, allowed = rejection
    if not isinstance(field, str) or not field:
        return None
    if reason == 'not_allowed' and isinstance(allowed, list) and allowed:
        value = allowed[0]
    elif reason == 'missing_required':
        value = _field_sample(capability_id, field)
        if value in (None, ''):
            return None
    else:
        return None
    key = (field, repr(value))
    if key in tried:
        return None
    tried.add(key)
    return field, value


def _post_accepting(path, payload, headers, capability_id=None):
    """POST the completed payload; when the product refuses a field AS
    DATA, adopt the value its own model declares and retry. Returns
    (response, corrections). Each (field, value) is tried at most once,
    so the loop converges or stops. A refusal that is not a field
    rejection (a 503 placeholder refusal, a 401) is returned as is."""
    payload = _sample_payload_for(capability_id, payload)
    corrections = []
    tried = set()
    resp = client.post(path, json=payload, headers=headers)
    for _ in range(len(payload) + 2):
        failed = resp.status_code not in _ACCEPT_STATUSES
        if not failed:
            try:
                failed = resp.json().get(_OK_KEY) is False
            except Exception:
                failed = False
        if not failed:
            break
        rejection = _rejection(resp)
        if rejection is None:
            break
        correction = _corrected(rejection, capability_id, tried)
        if correction is None:
            break
        field, value = correction
        corrections.append(
            str(field) + '=' + repr(payload.get(field)) + '->' + repr(value)
        )
        payload[field] = value
        resp = client.post(path, json=payload, headers=headers)
    if _still_failed(resp):
        _record_capability_failure(capability_id)
    return resp, corrections


def _still_failed(resp):
    if resp.status_code not in _ACCEPT_STATUSES:
        return True
    try:
        return resp.json().get(_OK_KEY) is False
    except Exception:
        return False


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


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == 'ok'
    assert body["ok"] is True
    names = {item["name"] for item in body["checks"]}
    assert set(['process', 'persistent_disk', 'database', 'migrations']) <= names
    assert all(item["ok"] for item in body["checks"])


def test_kernel_jobs_roster():
    """GET /v1/jobs publishes every kernel JD; distinctive routes answer."""
    resp = client.get("/v1/jobs", headers=AUTH)
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    by_kernel = {j["kernel"]: j for j in jobs}
    assert set(by_kernel) == set(['CLONER', 'COLLECTOR', 'STORE_MANAGER', 'TESTER', 'WRITER'])
    assert by_kernel['COLLECTOR']["title"] == 'Binding surveyor'
    assert by_kernel['CLONER']["title"] == 'Block stocker'
    assert by_kernel['WRITER']["title"] == 'Platform manufacturer'
    assert by_kernel['TESTER']["title"] == 'Acceptance inspector'
    assert by_kernel['STORE_MANAGER']["title"] == 'Store registrar'
    for job in jobs:
        assert job["mandate"] and job["http_routes"] and job["agent"]
    catalog = client.get("/v1/catalog", headers=AUTH)
    assert catalog.status_code == 200
    assert catalog.json()["kernel"] == 'COLLECTOR'
    inventory = client.get("/v1/inventory", headers=AUTH)
    assert inventory.status_code == 200
    assert inventory.json()["kernel"] == 'CLONER'
    assert "lock" in inventory.json()
    caps_resp = client.get("/v1/capabilities", headers=AUTH)
    assert caps_resp.status_code == 200
    assert isinstance(caps_resp.json()["items"], list)
    gates = client.get("/v1/gates", headers=AUTH)
    assert gates.status_code == 200
    assert gates.json()["kernel"] == 'TESTER'
    assert gates.json()["runs_over_http"] is False
    prov = client.get("/v1/provenance", headers=AUTH)
    assert prov.status_code == 200
    assert prov.json()["kernel"] == 'STORE_MANAGER'


def test_every_capability_route_answers():
    """Code-phase: each capability POST answers HTTP 200 JSON.
    Store ok: False is allowed here — acceptance is the pilot test."""
    failures = []
    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'customer_name': 'sample', 'customer_email': 'guest@example.com', 'contractor_reference': 'sample', 'suburb': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'end_time': '10:00:00', 'service_type': 'sample', 'quoted_amount': 1.0, 'cost_amount': 1.0}
    resp, _corr = _post_accepting("/v1/customer_booking_flow", payload, AUTH, 'customer_booking_flow')
    if resp.status_code not in (200,):
        failures.append('customer_booking_flow: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('customer_booking_flow: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('customer_booking_flow: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('customer_booking_flow: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/customer_booking_flow", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('customer_booking_flow list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_name': 'sample', 'contact_email': 'guest@example.com', 'phone': 'sample', 'service_suburbs': 'sample', 'pending_suburbs': 'sample', 'catalogue_state': 'sample', 'vehicle_type': 'sample', 'capacity': 1, 'active': True}
    resp, _corr = _post_accepting("/v1/contractor_onboarding_and_service_areas", payload, AUTH, 'contractor_onboarding_and_service_areas')
    if resp.status_code not in (200,):
        failures.append('contractor_onboarding_and_service_areas: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('contractor_onboarding_and_service_areas: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('contractor_onboarding_and_service_areas: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('contractor_onboarding_and_service_areas: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/contractor_onboarding_and_service_areas", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('contractor_onboarding_and_service_areas list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_reference': 'sample', 'weekday': 'monday', 'start_time': '10:00:00', 'end_time': '10:00:00', 'capacity': 1, 'active': True}
    resp, _corr = _post_accepting("/v1/contractor_availability_schedule", payload, AUTH, 'contractor_availability_schedule')
    if resp.status_code not in (200,):
        failures.append('contractor_availability_schedule: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('contractor_availability_schedule: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('contractor_availability_schedule: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('contractor_availability_schedule: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/contractor_availability_schedule", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('contractor_availability_schedule list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'suburb': 'sample', 'contractor_reference': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'distance_km': 1.0, 'required_skills': 'sample'}
    resp, _corr = _post_accepting("/v1/location_based_matching", payload, AUTH, 'location_based_matching')
    if resp.status_code not in (200,):
        failures.append('location_based_matching: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('location_based_matching: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('location_based_matching: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('location_based_matching: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/location_based_matching", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('location_based_matching list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'current_state': 'requested', 'target_state': 'requested', 'actor': 'customer', 'transition_id': 'sample'}
    resp, _corr = _post_accepting("/v1/booking_status_lifecycle", payload, AUTH, 'booking_status_lifecycle')
    if resp.status_code not in (200,):
        failures.append('booking_status_lifecycle: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('booking_status_lifecycle: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('booking_status_lifecycle: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('booking_status_lifecycle: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/booking_status_lifecycle", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('booking_status_lifecycle list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'recipient_email': 'guest@example.com', 'recipient_phone': 'sample', 'channel': 'email', 'message': 'sample', 'event_type': 'sample'}
    resp, _corr = _post_accepting("/v1/booking_notifications", payload, AUTH, 'booking_notifications')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS']):
        failures.append('booking_notifications: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/booking_notifications", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('booking_notifications list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'amount': 1.0, 'units': 1.0, 'payee_reference': 'sample', 'invoice_reference': 'sample', 'payout_stage': 'hold', 'released_amount': 1.0}
    resp, _corr = _post_accepting("/v1/invoicing_and_payouts", payload, AUTH, 'invoicing_and_payouts')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['ACCOUNTING_AND_TAX_VAT_SYSTEM_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS', 'PAYMENT_PROCESSOR_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS']):
        failures.append('invoicing_and_payouts: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming ACCOUNTING_AND_TAX_VAT_SYSTEM_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, PAYMENT_PROCESSOR_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/invoicing_and_payouts", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('invoicing_and_payouts list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'dispute_reference': 'sample', 'booking_reference': 'sample', 'claimant': 'sample', 'claim_type': 'sample', 'suburb': 'sample', 'region': 'sample', 'resolution_notes': 'sample', 'dispute_action': 'open', 'resolution': 'released', 'maintain_suburbs': True, 'suburb_active': True}
    resp, _corr = _post_accepting("/v1/ops_back_office", payload, AUTH, 'ops_back_office')
    if resp.status_code not in (200,):
        failures.append('ops_back_office: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('ops_back_office: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('ops_back_office: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('ops_back_office: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/ops_back_office", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('ops_back_office list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'event': 'sample', 'resource_type': 'sample', 'resource_id': 'sample', 'details': 'sample', 'actor': 'sample', 'sequence': 1, 'previous_digest': 'sample', 'chain_digest': 'sample'}
    resp, _corr = _post_accepting("/v1/audit", payload, AUTH, 'audit')
    if resp.status_code not in (200,):
        failures.append('audit: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('audit: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('audit: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('audit: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/audit", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('audit list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'config_block': 'sample', 'key': 'sample', 'value': 'sample'}
    resp, _corr = _post_accepting("/v1/config", payload, AUTH, 'config')
    if resp.status_code not in (200,):
        failures.append('config: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('config: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('config: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('config: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/config", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('config list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'recipient_email': 'guest@example.com', 'subject': 'sample', 'body': 'sample'}
    resp, _corr = _post_accepting("/v1/email", payload, AUTH, 'email')
    if resp.status_code not in (200,):
        failures.append('email: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('email: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('email: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('email: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/email", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('email list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'api_key': 'sample', 'block_used': 'sample', 'tokens': 1, 'plan': 'free'}
    resp, _corr = _post_accepting("/v1/billing", payload, AUTH, 'billing')
    if resp.status_code not in (200,):
        failures.append('billing: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('billing: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('billing: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('billing: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/billing", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('billing list: HTTP ' + str(listed.status_code))

    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_route_accepts_payload():
    """Pilot: spec payload is accepted (ok is not False) and persisted.
    Not the factory code-phase gate."""
    failures = []
    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'customer_name': 'sample', 'customer_email': 'guest@example.com', 'contractor_reference': 'sample', 'suburb': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'end_time': '10:00:00', 'service_type': 'sample', 'quoted_amount': 1.0, 'cost_amount': 1.0}
    resp, _corr = _post_accepting("/v1/customer_booking_flow", payload, AUTH, 'customer_booking_flow')
    if resp.status_code not in (200,):
        failures.append('customer_booking_flow: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('customer_booking_flow rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/customer_booking_flow", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('customer_booking_flow list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('customer_booking_flow list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('customer_booking_flow accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/customer_booking_flow/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('customer_booking_flow get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/customer_booking_flow/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('customer_booking_flow missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_name': 'sample', 'contact_email': 'guest@example.com', 'phone': 'sample', 'service_suburbs': 'sample', 'pending_suburbs': 'sample', 'catalogue_state': 'sample', 'vehicle_type': 'sample', 'capacity': 1, 'active': True}
    resp, _corr = _post_accepting("/v1/contractor_onboarding_and_service_areas", payload, AUTH, 'contractor_onboarding_and_service_areas')
    if resp.status_code not in (200,):
        failures.append('contractor_onboarding_and_service_areas: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('contractor_onboarding_and_service_areas rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/contractor_onboarding_and_service_areas", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('contractor_onboarding_and_service_areas list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('contractor_onboarding_and_service_areas list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('contractor_onboarding_and_service_areas accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/contractor_onboarding_and_service_areas/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('contractor_onboarding_and_service_areas get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/contractor_onboarding_and_service_areas/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('contractor_onboarding_and_service_areas missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_reference': 'sample', 'weekday': 'monday', 'start_time': '10:00:00', 'end_time': '10:00:00', 'capacity': 1, 'active': True}
    resp, _corr = _post_accepting("/v1/contractor_availability_schedule", payload, AUTH, 'contractor_availability_schedule')
    if resp.status_code not in (200,):
        failures.append('contractor_availability_schedule: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('contractor_availability_schedule rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/contractor_availability_schedule", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('contractor_availability_schedule list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('contractor_availability_schedule list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('contractor_availability_schedule accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/contractor_availability_schedule/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('contractor_availability_schedule get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/contractor_availability_schedule/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('contractor_availability_schedule missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'suburb': 'sample', 'contractor_reference': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'distance_km': 1.0, 'required_skills': 'sample'}
    resp, _corr = _post_accepting("/v1/location_based_matching", payload, AUTH, 'location_based_matching')
    if resp.status_code not in (200,):
        failures.append('location_based_matching: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('location_based_matching rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/location_based_matching", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('location_based_matching list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('location_based_matching list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('location_based_matching accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/location_based_matching/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('location_based_matching get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/location_based_matching/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('location_based_matching missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'current_state': 'requested', 'target_state': 'requested', 'actor': 'customer', 'transition_id': 'sample'}
    resp, _corr = _post_accepting("/v1/booking_status_lifecycle", payload, AUTH, 'booking_status_lifecycle')
    if resp.status_code not in (200,):
        failures.append('booking_status_lifecycle: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('booking_status_lifecycle rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/booking_status_lifecycle", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('booking_status_lifecycle list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('booking_status_lifecycle list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('booking_status_lifecycle accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/booking_status_lifecycle/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('booking_status_lifecycle get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/booking_status_lifecycle/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('booking_status_lifecycle missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'recipient_email': 'guest@example.com', 'recipient_phone': 'sample', 'channel': 'email', 'message': 'sample', 'event_type': 'sample'}
    resp, _corr = _post_accepting("/v1/booking_notifications", payload, AUTH, 'booking_notifications')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS']):
        failures.append('booking_notifications: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/booking_notifications", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('booking_notifications list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'amount': 1.0, 'units': 1.0, 'payee_reference': 'sample', 'invoice_reference': 'sample', 'payout_stage': 'hold', 'released_amount': 1.0}
    resp, _corr = _post_accepting("/v1/invoicing_and_payouts", payload, AUTH, 'invoicing_and_payouts')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['ACCOUNTING_AND_TAX_VAT_SYSTEM_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS', 'PAYMENT_PROCESSOR_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS']):
        failures.append('invoicing_and_payouts: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming ACCOUNTING_AND_TAX_VAT_SYSTEM_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, PAYMENT_PROCESSOR_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/invoicing_and_payouts", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('invoicing_and_payouts list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'dispute_reference': 'sample', 'booking_reference': 'sample', 'claimant': 'sample', 'claim_type': 'sample', 'suburb': 'sample', 'region': 'sample', 'resolution_notes': 'sample', 'dispute_action': 'open', 'resolution': 'released', 'maintain_suburbs': True, 'suburb_active': True}
    resp, _corr = _post_accepting("/v1/ops_back_office", payload, AUTH, 'ops_back_office')
    if resp.status_code not in (200,):
        failures.append('ops_back_office: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('ops_back_office rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/ops_back_office", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('ops_back_office list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('ops_back_office list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('ops_back_office accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/ops_back_office/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('ops_back_office get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/ops_back_office/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('ops_back_office missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'event': 'sample', 'resource_type': 'sample', 'resource_id': 'sample', 'details': 'sample', 'actor': 'sample', 'sequence': 1, 'previous_digest': 'sample', 'chain_digest': 'sample'}
    resp, _corr = _post_accepting("/v1/audit", payload, AUTH, 'audit')
    if resp.status_code not in (200,):
        failures.append('audit: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('audit rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/audit", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('audit list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('audit list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('audit accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/audit/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('audit get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/audit/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('audit missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'config_block': 'sample', 'key': 'sample', 'value': 'sample'}
    resp, _corr = _post_accepting("/v1/config", payload, AUTH, 'config')
    if resp.status_code not in (200,):
        failures.append('config: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('config rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/config", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('config list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('config list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('config accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/config/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('config get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/config/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('config missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'recipient_email': 'guest@example.com', 'subject': 'sample', 'body': 'sample'}
    resp, _corr = _post_accepting("/v1/email", payload, AUTH, 'email')
    if resp.status_code not in (200,):
        failures.append('email: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('email rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/email", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('email list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('email list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('email accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/email/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('email get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/email/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('email missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'notes': 'sample', 'api_key': 'sample', 'block_used': 'sample', 'tokens': 1, 'plan': 'free'}
    resp, _corr = _post_accepting("/v1/billing", payload, AUTH, 'billing')
    if resp.status_code not in (200,):
        failures.append('billing: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('billing rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/billing", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('billing list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('billing list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('billing accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/billing/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('billing get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/billing/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('billing missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    assert not failures, "; ".join(failures)
