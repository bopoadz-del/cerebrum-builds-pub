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
    payload = {'reference': 'sample', 'status': 'open', 'schema_version': 'sample'}
    resp, _corr = _post_accepting("/v1/track_loader", payload, AUTH, 'track_loader')
    if resp.status_code not in (200,):
        failures.append('track_loader: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('track_loader: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('track_loader: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('track_loader: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/track_loader", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('track_loader list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    resp, _corr = _post_accepting("/v1/enrolment_and_calendar", payload, AUTH, 'enrolment_and_calendar')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['EMAIL_DELIVERY_CREDENTIALS']):
        failures.append('enrolment_and_calendar: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming EMAIL_DELIVERY_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/enrolment_and_calendar", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('enrolment_and_calendar list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    resp, _corr = _post_accepting("/v1/faculty_session", payload, AUTH, 'faculty_session')
    if resp.status_code not in (200,):
        failures.append('faculty_session: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('faculty_session: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('faculty_session: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('faculty_session: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/faculty_session", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('faculty_session list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    resp, _corr = _post_accepting("/v1/memo_grading", payload, AUTH, 'memo_grading')
    if resp.status_code not in (200,):
        failures.append('memo_grading: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('memo_grading: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('memo_grading: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('memo_grading: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/memo_grading", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('memo_grading list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    resp, _corr = _post_accepting("/v1/gradebook_and_transcript", payload, AUTH, 'gradebook_and_transcript')
    if resp.status_code not in (200,):
        failures.append('gradebook_and_transcript: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('gradebook_and_transcript: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('gradebook_and_transcript: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('gradebook_and_transcript: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/gradebook_and_transcript", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('gradebook_and_transcript list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    resp, _corr = _post_accepting("/v1/defense_and_capstone", payload, AUTH, 'defense_and_capstone')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['EMAIL_DELIVERY_CREDENTIALS']):
        failures.append('defense_and_capstone: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming EMAIL_DELIVERY_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/defense_and_capstone", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('defense_and_capstone list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'}
    resp, _corr = _post_accepting("/v1/track_admin", payload, AUTH, 'track_admin')
    if resp.status_code not in (200,):
        failures.append('track_admin: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('track_admin: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('track_admin: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('track_admin: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/track_admin", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('track_admin list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    resp, _corr = _post_accepting("/v1/reading_and_case_library", payload, AUTH, 'reading_and_case_library')
    if resp.status_code not in (200,):
        failures.append('reading_and_case_library: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        try:
            body = resp.json()
        except Exception:
            failures.append('reading_and_case_library: response is not JSON')
        else:
            if not isinstance(body, dict):
                failures.append('reading_and_case_library: JSON body is not a dict')
            # A connector with no credentials answers as a DECLARED
            # STUB -- ok:true, naming what is unavailable. That IS the
            # right answer before the operator configures it. Judged
            # only when THIS response declares itself a stub at the top
            # level; a stubbed block nested inside a capability's result
            # is that capability's business, and ok:false stays allowed.
            elif 'blocks_unavailable' in body:
                unavailable = body.get('blocks_unavailable')
                if body.get('ok') is not True or not unavailable:
                    failures.append('reading_and_case_library: declared stub must be ok:true' + ' and name blocks_unavailable')
            listed = client.get("/v1/reading_and_case_library", headers=AUTH)
            if listed.status_code not in (200,):
                failures.append('reading_and_case_library list: HTTP ' + str(listed.status_code))

    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_route_accepts_payload():
    """Pilot: spec payload is accepted (ok is not False) and persisted.
    Not the factory code-phase gate."""
    failures = []
    payload = {'reference': 'sample', 'status': 'open', 'schema_version': 'sample'}
    resp, _corr = _post_accepting("/v1/track_loader", payload, AUTH, 'track_loader')
    if resp.status_code not in (200,):
        failures.append('track_loader: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('track_loader rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/track_loader", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('track_loader list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('track_loader list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('track_loader accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/track_loader/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('track_loader get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/track_loader/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('track_loader missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'}
    resp, _corr = _post_accepting("/v1/enrolment_and_calendar", payload, AUTH, 'enrolment_and_calendar')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['EMAIL_DELIVERY_CREDENTIALS']):
        failures.append('enrolment_and_calendar: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming EMAIL_DELIVERY_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/enrolment_and_calendar", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('enrolment_and_calendar list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'}
    resp, _corr = _post_accepting("/v1/faculty_session", payload, AUTH, 'faculty_session')
    if resp.status_code not in (200,):
        failures.append('faculty_session: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('faculty_session rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/faculty_session", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('faculty_session list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('faculty_session list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('faculty_session accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/faculty_session/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('faculty_session get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/faculty_session/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('faculty_session missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'}
    resp, _corr = _post_accepting("/v1/memo_grading", payload, AUTH, 'memo_grading')
    if resp.status_code not in (200,):
        failures.append('memo_grading: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('memo_grading rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/memo_grading", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('memo_grading list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('memo_grading list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('memo_grading accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/memo_grading/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('memo_grading get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/memo_grading/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('memo_grading missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'}
    resp, _corr = _post_accepting("/v1/gradebook_and_transcript", payload, AUTH, 'gradebook_and_transcript')
    if resp.status_code not in (200,):
        failures.append('gradebook_and_transcript: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('gradebook_and_transcript rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/gradebook_and_transcript", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('gradebook_and_transcript list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('gradebook_and_transcript list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('gradebook_and_transcript accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/gradebook_and_transcript/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('gradebook_and_transcript get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/gradebook_and_transcript/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('gradebook_and_transcript missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1}
    resp, _corr = _post_accepting("/v1/defense_and_capstone", payload, AUTH, 'defense_and_capstone')
    try:
        body = resp.json()
    except Exception:
        body = None
    if not (resp.status_code == 503
            and isinstance(body, dict) and body.get('ok') is False
            and body.get('error_kind') == 'unavailable'
            and list(body.get('settings') or []) == ['EMAIL_DELIVERY_CREDENTIALS']):
        failures.append('defense_and_capstone: declares placeholder connector(s); want HTTP 503 error_kind unavailable naming EMAIL_DELIVERY_CREDENTIALS, got HTTP ' + str(resp.status_code) + ': ' + resp.text[:200])
    listed = client.get("/v1/defense_and_capstone", headers=AUTH)
    if listed.status_code not in (200,):
        failures.append('defense_and_capstone list: HTTP ' + str(listed.status_code))

    payload = {'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'}
    resp, _corr = _post_accepting("/v1/track_admin", payload, AUTH, 'track_admin')
    if resp.status_code not in (200,):
        failures.append('track_admin: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('track_admin rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/track_admin", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('track_admin list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('track_admin list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('track_admin accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/track_admin/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('track_admin get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/track_admin/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('track_admin missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    payload = {'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1}
    resp, _corr = _post_accepting("/v1/reading_and_case_library", payload, AUTH, 'reading_and_case_library')
    if resp.status_code not in (200,):
        failures.append('reading_and_case_library: HTTP ' + str(resp.status_code) + ': ' + resp.text[:200] + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    elif resp.json().get('ok') is False:
        failures.append('reading_and_case_library rejected a payload built from its own schema: ' + str(resp.json().get('error')) + (' [tester already tried the values the route named: ' + '; '.join(_corr) + ']' if _corr else ''))
    else:
        listed = client.get("/v1/reading_and_case_library", headers=AUTH)
        listed_body = listed.json() if listed.content else {}
        if listed.status_code not in (200,):
            failures.append('reading_and_case_library list: HTTP ' + str(listed.status_code))
        elif isinstance(listed_body, dict) and listed_body.get('ok') is False:
            failures.append('reading_and_case_library list refused: ' + str(listed_body.get('error') or listed_body)[:200])
        else:
            rows = _listed(listed_body)
            if not rows:
                failures.append('reading_and_case_library accepted a record but persisted nothing')
            else:
                item_id = rows[0].get('id')
                got = client.get(f"/v1/reading_and_case_library/{item_id}", headers=AUTH)
                if got.status_code not in (200,):
                    failures.append('reading_and_case_library get: HTTP ' + str(got.status_code))
                missing = client.get("/v1/reading_and_case_library/999999", headers=AUTH)
                if missing.status_code != 404:
                    failures.append('reading_and_case_library missing id: HTTP ' + str(missing.status_code) + ' (expected 404)')

    assert not failures, "; ".join(failures)
