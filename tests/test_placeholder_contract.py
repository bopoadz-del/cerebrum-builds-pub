"""What a capability calling a DECLARED placeholder connector answers.

Written by the Factory from the blueprint. This file is the authority:
a test elsewhere that expects a live answer from these capabilities is
a test defect, not a product failure."""

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer " + os.environ["PLATFORM_TOKEN"]}


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
    if not isinstance(body, dict) or 'rejected_field' not in body:
        return None
    return (body.get('rejected_field'), body.get('rejection_reason'),
            body.get('allowed_values'))


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
        field, reason, allowed = rejection
        if not isinstance(field, str) or not field:
            break
        if reason == 'not_allowed' and isinstance(allowed, list) and allowed:
            value = allowed[0]
        elif reason == 'missing_required':
            value = _field_sample(capability_id, field)
            if value in (None, ''):
                break
        else:
            break
        key = (field, repr(value))
        if key in tried:
            break
        tried.add(key)
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


def test_cost_price_movement_alerts_answers_the_declared_unavailable_refusal():
    before = client.get("/v1/cost_price_movement_alerts", headers=AUTH)
    resp, _corr = _post_accepting("/v1/cost_price_movement_alerts", {'reference': 'sample', 'status': 'open', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}, AUTH, 'cost_price_movement_alerts')
    assert resp.status_code == 503, resp.text[:300]
    body = resp.json()
    assert body['ok'] is False
    assert body['error_kind'] == 'unavailable'
    assert body['settings'] == ['OUTLOOK_CREDENTIALS']
    # Refused before the handler: nothing was stored.
    after = client.get("/v1/cost_price_movement_alerts", headers=AUTH)
    assert after.status_code in (200,)
    assert after.json() == before.json()


def test_document_ingestion_from_m365_and_upload_answers_the_declared_unavailable_refusal():
    before = client.get("/v1/document_ingestion_from_m365_and_upload", headers=AUTH)
    resp, _corr = _post_accepting("/v1/document_ingestion_from_m365_and_upload", {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}, AUTH, 'document_ingestion_from_m365_and_upload')
    assert resp.status_code == 503, resp.text[:300]
    body = resp.json()
    assert body['ok'] is False
    assert body['error_kind'] == 'unavailable'
    assert body['settings'] == ['OUTLOOK_CREDENTIALS']
    # Refused before the handler: nothing was stored.
    after = client.get("/v1/document_ingestion_from_m365_and_upload", headers=AUTH)
    assert after.status_code in (200,)
    assert after.json() == before.json()


def test_supplier_cost_and_parts_pricing_answers_the_declared_unavailable_refusal():
    before = client.get("/v1/supplier_cost_and_parts_pricing", headers=AUTH)
    resp, _corr = _post_accepting("/v1/supplier_cost_and_parts_pricing", {'reference': 'sample', 'status': 'open', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}, AUTH, 'supplier_cost_and_parts_pricing')
    assert resp.status_code == 503, resp.text[:300]
    body = resp.json()
    assert body['ok'] is False
    assert body['error_kind'] == 'unavailable'
    assert body['settings'] == ['SAP_ERP_CREDENTIALS']
    # Refused before the handler: nothing was stored.
    after = client.get("/v1/supplier_cost_and_parts_pricing", headers=AUTH)
    assert after.status_code in (200,)
    assert after.json() == before.json()
