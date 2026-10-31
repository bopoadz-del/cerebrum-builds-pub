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
    payload = {'reference': 'sample', 'status': 'open', 'question': 'sample', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    resp, _corr = _post_accepting("/v1/document_grounded_qa", payload, AUTH, 'document_grounded_qa')
    if resp.status_code not in (200,):
        failures.append('document_grounded_qa: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('document_grounded_qa: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('document_grounded_qa: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('document_grounded_qa: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/document_grounded_qa", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('document_grounded_qa list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    resp, _corr = _post_accepting("/v1/supplier_cost_and_parts_pricing", payload, AUTH, 'supplier_cost_and_parts_pricing')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['SAP_ERP_CREDENTIALS']):
        failures.append('supplier_cost_and_parts_pricing: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming SAP_ERP_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/supplier_cost_and_parts_pricing", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('supplier_cost_and_parts_pricing list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    resp, _corr = _post_accepting("/v1/cost_price_movement_alerts", payload, AUTH, 'cost_price_movement_alerts')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['OUTLOOK_CREDENTIALS']):
        failures.append('cost_price_movement_alerts: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming OUTLOOK_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/cost_price_movement_alerts", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('cost_price_movement_alerts list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    resp, _corr = _post_accepting("/v1/document_revision_nudges", payload, AUTH, 'document_revision_nudges')
    if resp.status_code not in (200,):
        failures.append('document_revision_nudges: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('document_revision_nudges: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('document_revision_nudges: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('document_revision_nudges: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/document_revision_nudges", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('document_revision_nudges list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    resp, _corr = _post_accepting("/v1/document_ingestion_from_m365_and_upload", payload, AUTH, 'document_ingestion_from_m365_and_upload')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['OUTLOOK_CREDENTIALS']):
        failures.append('document_ingestion_from_m365_and_upload: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming OUTLOOK_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/document_ingestion_from_m365_and_upload", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('document_ingestion_from_m365_and_upload list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'plant': 'plant-casablanca', 'period_start': '2026-09-03', 'period_end': '2026-09-03', 'include_alerts': True, 'layout': 'sample'}
    resp, _corr = _post_accepting("/v1/manager_dashboard", payload, AUTH, 'manager_dashboard')
    if resp.status_code not in (200,):
        failures.append('manager_dashboard: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('manager_dashboard: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('manager_dashboard: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('manager_dashboard: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/manager_dashboard", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('manager_dashboard list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'manager_name': 'sample', 'manager_email': 'guest@example.com', 'role': 'manager', 'plant': 'plant-casablanca'}
    resp, _corr = _post_accepting("/v1/manager_only_access", payload, AUTH, 'manager_only_access')
    if resp.status_code not in (200,):
        failures.append('manager_only_access: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('manager_only_access: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('manager_only_access: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('manager_only_access: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/manager_only_access", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('manager_only_access list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'company_code': 'sample', 'operation': 'status', 'base_url': 'sample'}
    resp, _corr = _post_accepting("/v1/sap_odata_connector", payload, AUTH, 'sap_odata_connector')
    if resp.status_code not in (200,):
        failures.append('sap_odata_connector: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('sap_odata_connector: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('sap_odata_connector: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('sap_odata_connector: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/sap_odata_connector", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('sap_odata_connector list: HTTP ' + str(listed.status_code))

    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_route_accepts_payload():
    """Pilot: spec payload is accepted (ok is not False) and persisted.
    Not the factory code-phase gate."""
    failures = []
    payload = {'reference': 'sample', 'status': 'open', 'question': 'sample', 'plant': 'plant-casablanca', 'document_type': 'bom', 'top_k': 1, 'answer': 'sample', 'authority': 'sample', 'tenant_scope': 'sample'}
    resp, _corr = _post_accepting("/v1/document_grounded_qa", payload, AUTH, 'document_grounded_qa')
    if resp.status_code not in (200,):
        failures.append('document_grounded_qa: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('document_grounded_qa rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/document_grounded_qa", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('document_grounded_qa list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('document_grounded_qa list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('document_grounded_qa accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/document_grounded_qa/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('document_grounded_qa get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/document_grounded_qa/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('document_grounded_qa missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'invoice_reference': 'sample', 'supplier': 'sample', 'part_number': 'sample', 'amount_mad': 1.0, 'quantity': 1, 'unit_cost_mad': 1.0, 'price_mad': 1.0, 'plant': 'plant-casablanca', 'invoice_date': '2026-09-03', 'markup_ratio': 1.5}
    resp, _corr = _post_accepting("/v1/supplier_cost_and_parts_pricing", payload, AUTH, 'supplier_cost_and_parts_pricing')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['SAP_ERP_CREDENTIALS']):
        failures.append('supplier_cost_and_parts_pricing: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming SAP_ERP_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/supplier_cost_and_parts_pricing", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('supplier_cost_and_parts_pricing list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'alert_reference': 'sample', 'part_number': 'sample', 'supplier': 'sample', 'threshold_mad': 1.0, 'movement_pct': 1.5, 'previous_price_mad': 1.0, 'current_price_mad': 1.0, 'alert_level': 'info', 'plant': 'plant-casablanca', 'notified': True}
    resp, _corr = _post_accepting("/v1/cost_price_movement_alerts", payload, AUTH, 'cost_price_movement_alerts')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['OUTLOOK_CREDENTIALS']):
        failures.append('cost_price_movement_alerts: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming OUTLOOK_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/cost_price_movement_alerts", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('cost_price_movement_alerts list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'document_type': 'bom', 'revision_from': 'sample', 'revision_to': 'sample', 'manager_email': 'guest@example.com', 'plant': 'plant-casablanca', 'notified': True}
    resp, _corr = _post_accepting("/v1/document_revision_nudges", payload, AUTH, 'document_revision_nudges')
    if resp.status_code not in (200,):
        failures.append('document_revision_nudges: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('document_revision_nudges rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/document_revision_nudges", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('document_revision_nudges list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('document_revision_nudges list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('document_revision_nudges accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/document_revision_nudges/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('document_revision_nudges get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/document_revision_nudges/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('document_revision_nudges missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'document_name': 'sample', 'source': 'onedrive', 'document_type': 'bom', 'content_text': 'sample', 'drive_item_id': 'sample', 'plant': 'plant-casablanca'}
    resp, _corr = _post_accepting("/v1/document_ingestion_from_m365_and_upload", payload, AUTH, 'document_ingestion_from_m365_and_upload')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['OUTLOOK_CREDENTIALS']):
        failures.append('document_ingestion_from_m365_and_upload: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming OUTLOOK_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/document_ingestion_from_m365_and_upload", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('document_ingestion_from_m365_and_upload list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'plant': 'plant-casablanca', 'period_start': '2026-09-03', 'period_end': '2026-09-03', 'include_alerts': True, 'layout': 'sample'}
    resp, _corr = _post_accepting("/v1/manager_dashboard", payload, AUTH, 'manager_dashboard')
    if resp.status_code not in (200,):
        failures.append('manager_dashboard: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('manager_dashboard rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/manager_dashboard", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('manager_dashboard list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('manager_dashboard list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('manager_dashboard accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/manager_dashboard/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('manager_dashboard get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/manager_dashboard/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('manager_dashboard missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'manager_name': 'sample', 'manager_email': 'guest@example.com', 'role': 'manager', 'plant': 'plant-casablanca'}
    resp, _corr = _post_accepting("/v1/manager_only_access", payload, AUTH, 'manager_only_access')
    if resp.status_code not in (200,):
        failures.append('manager_only_access: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('manager_only_access rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/manager_only_access", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('manager_only_access list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('manager_only_access list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('manager_only_access accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/manager_only_access/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('manager_only_access get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/manager_only_access/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('manager_only_access missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'company_code': 'sample', 'operation': 'status', 'base_url': 'sample'}
    resp, _corr = _post_accepting("/v1/sap_odata_connector", payload, AUTH, 'sap_odata_connector')
    if resp.status_code not in (200,):
        failures.append('sap_odata_connector: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('sap_odata_connector rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/sap_odata_connector", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('sap_odata_connector list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('sap_odata_connector list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('sap_odata_connector accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/sap_odata_connector/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('sap_odata_connector get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/sap_odata_connector/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('sap_odata_connector missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    assert not failures, "; ".join(failures)
