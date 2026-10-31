"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import document_grounded_qa
    assert document_grounded_qa.CAPABILITY_ID
    from app.actions import supplier_cost_and_parts_pricing
    assert supplier_cost_and_parts_pricing.CAPABILITY_ID
    from app.actions import cost_price_movement_alerts
    assert cost_price_movement_alerts.CAPABILITY_ID
    from app.actions import document_revision_nudges
    assert document_revision_nudges.CAPABILITY_ID
    from app.actions import document_ingestion_from_m365_and_upload
    assert document_ingestion_from_m365_and_upload.CAPABILITY_ID
    from app.actions import manager_dashboard
    assert manager_dashboard.CAPABILITY_ID
    from app.actions import manager_only_access
    assert manager_only_access.CAPABILITY_ID
    from app.actions import sap_odata_connector
    assert sap_odata_connector.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['aesthetic_kit', 'analytics', 'approval_rules', 'audit', 'auth', 'capture', 'dashboard', 'email', 'finance_canonical_model', 'finance_data_quality', 'finance_import', 'finance_reconciliation', 'ingestion_provenance', 'knowledge', 'llm_enhancer', 'microsoft_365', 'multi_tenant_rbac', 'notification', 'ocr', 'onedrive', 'pdf', 'sap_odata_connector', 'search', 'user_auth', 'validation', 'vector_search', 'version_diff']:
        load_block(block_id)
    actions = {}
    for block_id in ['aesthetic_kit', 'analytics', 'approval_rules', 'audit', 'auth', 'capture', 'dashboard', 'email', 'finance_canonical_model', 'finance_data_quality', 'finance_import', 'finance_reconciliation', 'ingestion_provenance', 'knowledge', 'llm_enhancer', 'microsoft_365', 'multi_tenant_rbac', 'notification', 'ocr', 'onedrive', 'pdf', 'sap_odata_connector', 'search', 'user_auth', 'validation', 'vector_search', 'version_diff']:
        try:
            result = execute(block_id, {}, action=actions.get(block_id))
        except RuntimeError as exc:
            # The block ran and refused the empty probe -- fine here;
            # the pilot test below demands Store-backed success.
            # An import error is never fine.
            assert "No module named" not in str(exc), (block_id, exc)
            assert "cannot import" not in str(exc), (block_id, exc)
        else:
            assert isinstance(result, dict), block_id


def test_kit_packs_present():
    """The download is a product tree: kits/ next to vendor/blocks."""
    from pathlib import Path as _Path
    kits = _Path(__file__).resolve().parents[1] / "kits"
    assert kits.is_dir(), "kits/ missing from the delivered platform"
    assert list(kits.glob("*/manifest.json")), "no kit pack manifests"


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


def test_every_capability_handle_returns_mapping():
    """Code-phase: the coder wired handle() and it returns a dict.
    Store ok: False or a Store exception is not this gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    failures = []
    from app.actions import document_grounded_qa
    try:
        out = document_grounded_qa.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_grounded_qa handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_grounded_qa')
    from app.actions import supplier_cost_and_parts_pricing
    try:
        out = supplier_cost_and_parts_pricing.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('supplier_cost_and_parts_pricing handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('supplier_cost_and_parts_pricing')
    from app.actions import cost_price_movement_alerts
    try:
        out = cost_price_movement_alerts.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('cost_price_movement_alerts handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('cost_price_movement_alerts')
    from app.actions import document_revision_nudges
    try:
        out = document_revision_nudges.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_revision_nudges handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_revision_nudges')
    from app.actions import document_ingestion_from_m365_and_upload
    try:
        out = document_ingestion_from_m365_and_upload.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_ingestion_from_m365_and_upload handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_ingestion_from_m365_and_upload')
    from app.actions import manager_dashboard
    try:
        out = manager_dashboard.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('manager_dashboard handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('manager_dashboard')
    from app.actions import manager_only_access
    try:
        out = manager_only_access.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('manager_only_access handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('manager_only_access')
    from app.actions import sap_odata_connector
    try:
        out = sap_odata_connector.handle({})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('sap_odata_connector handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('sap_odata_connector')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import document_grounded_qa
    out = document_grounded_qa.handle({})
    if not isinstance(out, dict):
        failures.append('document_grounded_qa returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_grounded_qa')
    elif out.get('ok') is False:
        failures.append('document_grounded_qa rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_grounded_qa')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_grounded_qa reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_grounded_qa')
    from app.actions import supplier_cost_and_parts_pricing
    out = supplier_cost_and_parts_pricing.handle({})
    if not isinstance(out, dict):
        failures.append('supplier_cost_and_parts_pricing returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('supplier_cost_and_parts_pricing')
    elif out.get('ok') is False:
        failures.append('supplier_cost_and_parts_pricing rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('supplier_cost_and_parts_pricing')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('supplier_cost_and_parts_pricing reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('supplier_cost_and_parts_pricing')
    from app.actions import cost_price_movement_alerts
    out = cost_price_movement_alerts.handle({})
    if not isinstance(out, dict):
        failures.append('cost_price_movement_alerts returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('cost_price_movement_alerts')
    elif out.get('ok') is False:
        failures.append('cost_price_movement_alerts rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('cost_price_movement_alerts')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('cost_price_movement_alerts reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('cost_price_movement_alerts')
    from app.actions import document_revision_nudges
    out = document_revision_nudges.handle({})
    if not isinstance(out, dict):
        failures.append('document_revision_nudges returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_revision_nudges')
    elif out.get('ok') is False:
        failures.append('document_revision_nudges rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_revision_nudges')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_revision_nudges reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_revision_nudges')
    from app.actions import document_ingestion_from_m365_and_upload
    out = document_ingestion_from_m365_and_upload.handle({})
    if not isinstance(out, dict):
        failures.append('document_ingestion_from_m365_and_upload returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_ingestion_from_m365_and_upload')
    elif out.get('ok') is False:
        failures.append('document_ingestion_from_m365_and_upload rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_ingestion_from_m365_and_upload')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_ingestion_from_m365_and_upload reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_ingestion_from_m365_and_upload')
    from app.actions import manager_dashboard
    out = manager_dashboard.handle({})
    if not isinstance(out, dict):
        failures.append('manager_dashboard returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('manager_dashboard')
    elif out.get('ok') is False:
        failures.append('manager_dashboard rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('manager_dashboard')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('manager_dashboard reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('manager_dashboard')
    from app.actions import manager_only_access
    out = manager_only_access.handle({})
    if not isinstance(out, dict):
        failures.append('manager_only_access returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('manager_only_access')
    elif out.get('ok') is False:
        failures.append('manager_only_access rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('manager_only_access')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('manager_only_access reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('manager_only_access')
    from app.actions import sap_odata_connector
    out = sap_odata_connector.handle({})
    if not isinstance(out, dict):
        failures.append('sap_odata_connector returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('sap_odata_connector')
    elif out.get('ok') is False:
        failures.append('sap_odata_connector rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('sap_odata_connector')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('sap_odata_connector reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('sap_odata_connector')
    assert not failures, "; ".join(failures)
