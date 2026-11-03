"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import progress_claims
    assert progress_claims.CAPABILITY_ID
    from app.actions import delay_damages_tracking
    assert delay_damages_tracking.CAPABILITY_ID
    from app.actions import qa_itp_records
    assert qa_itp_records.CAPABILITY_ID
    from app.actions import document_register
    assert document_register.CAPABILITY_ID
    from app.actions import performance_security_tracking
    assert performance_security_tracking.CAPABILITY_ID
    from app.actions import defects_notification_period
    assert defects_notification_period.CAPABILITY_ID
    from app.actions import claim_evidence_and_approvals
    assert claim_evidence_and_approvals.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['analytics', 'approval_rules', 'audit', 'audit_chain', 'construction_advisor', 'cpm_engine', 'dashboard', 'document_engine', 'estate_maintenance', 'evidence_chain', 'evidence_classifier', 'evidence_or_refuse', 'evidence_verifier', 'finance_reconciliation', 'finance_reconciliation_workflow', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'notification', 'search', 'storage', 'validation', 'version_diff', 'workflow']:
        load_block(block_id)
    actions = {}
    for block_id in ['analytics', 'approval_rules', 'audit', 'audit_chain', 'construction_advisor', 'cpm_engine', 'dashboard', 'document_engine', 'estate_maintenance', 'evidence_chain', 'evidence_classifier', 'evidence_or_refuse', 'evidence_verifier', 'finance_reconciliation', 'finance_reconciliation_workflow', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'notification', 'search', 'storage', 'validation', 'version_diff', 'workflow']:
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
    from app.actions import progress_claims
    try:
        out = progress_claims.handle({'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'period': 'sample', 'gross_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5, 'currency': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('progress_claims handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('progress_claims')
    from app.actions import delay_damages_tracking
    try:
        out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'accepted_contract_amount': 1.5, 'delay_days': 'email', 'delay_damages': 1.5, 'cap_reached': True})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('delay_damages_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('delay_damages_tracking')
    from app.actions import qa_itp_records
    try:
        out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'boq_item': 'sample', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'sample', 'inspection_date': '2026-09-03'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('qa_itp_records handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('qa_itp_records')
    from app.actions import document_register
    try:
        out = document_register.handle({'reference': 'sample', 'status': 'open', 'title': 'sample', 'revision': 'sample', 'document_type': 'contract', 'source_filename': 'sample', 'checksum': 'sample', 'issued_date': '2026-09-03'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_register handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_register')
    from app.actions import performance_security_tracking
    try:
        out = performance_security_tracking.handle({'reference': 'sample', 'status': 'open', 'instrument_number': 'sample', 'accepted_contract_amount': 1.5, 'security_amount': 1.5, 'expiry_date': '2026-09-03', 'issuer': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('performance_security_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('performance_security_tracking')
    from app.actions import defects_notification_period
    try:
        out = defects_notification_period.handle({'reference': 'sample', 'status': 'open', 'taking_over_date': '2026-09-03', 'defect_ref': 'sample', 'defect_description': 'sample', 'closeout_evidence': 'sample', 'retention_release_amount': 1.5})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('defects_notification_period handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('defects_notification_period')
    from app.actions import claim_evidence_and_approvals
    try:
        out = claim_evidence_and_approvals.handle({'reference': 'sample', 'status': 'open', 'claim_reference': 'sample', 'evidence_ref': 'sample', 'preparer_id': 'sample', 'certifier_id': 'sample', 'decision': 'sample', 'claim_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('claim_evidence_and_approvals handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('claim_evidence_and_approvals')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import progress_claims
    out = progress_claims.handle({'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'period': 'sample', 'gross_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5, 'currency': 'sample'})
    if not isinstance(out, dict):
        failures.append('progress_claims returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('progress_claims')
    elif out.get('ok') is False:
        failures.append('progress_claims rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('progress_claims')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('progress_claims reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('progress_claims')
    from app.actions import delay_damages_tracking
    out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'accepted_contract_amount': 1.5, 'delay_days': 'email', 'delay_damages': 1.5, 'cap_reached': True})
    if not isinstance(out, dict):
        failures.append('delay_damages_tracking returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('delay_damages_tracking')
    elif out.get('ok') is False:
        failures.append('delay_damages_tracking rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('delay_damages_tracking')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('delay_damages_tracking reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('delay_damages_tracking')
    from app.actions import qa_itp_records
    out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'boq_item': 'sample', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'sample', 'inspection_date': '2026-09-03'})
    if not isinstance(out, dict):
        failures.append('qa_itp_records returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('qa_itp_records')
    elif out.get('ok') is False:
        failures.append('qa_itp_records rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('qa_itp_records')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('qa_itp_records reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('qa_itp_records')
    from app.actions import document_register
    out = document_register.handle({'reference': 'sample', 'status': 'open', 'title': 'sample', 'revision': 'sample', 'document_type': 'contract', 'source_filename': 'sample', 'checksum': 'sample', 'issued_date': '2026-09-03'})
    if not isinstance(out, dict):
        failures.append('document_register returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_register')
    elif out.get('ok') is False:
        failures.append('document_register rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_register')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_register reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_register')
    from app.actions import performance_security_tracking
    out = performance_security_tracking.handle({'reference': 'sample', 'status': 'open', 'instrument_number': 'sample', 'accepted_contract_amount': 1.5, 'security_amount': 1.5, 'expiry_date': '2026-09-03', 'issuer': 'sample'})
    if not isinstance(out, dict):
        failures.append('performance_security_tracking returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('performance_security_tracking')
    elif out.get('ok') is False:
        failures.append('performance_security_tracking rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('performance_security_tracking')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('performance_security_tracking reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('performance_security_tracking')
    from app.actions import defects_notification_period
    out = defects_notification_period.handle({'reference': 'sample', 'status': 'open', 'taking_over_date': '2026-09-03', 'defect_ref': 'sample', 'defect_description': 'sample', 'closeout_evidence': 'sample', 'retention_release_amount': 1.5})
    if not isinstance(out, dict):
        failures.append('defects_notification_period returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('defects_notification_period')
    elif out.get('ok') is False:
        failures.append('defects_notification_period rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('defects_notification_period')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('defects_notification_period reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('defects_notification_period')
    from app.actions import claim_evidence_and_approvals
    out = claim_evidence_and_approvals.handle({'reference': 'sample', 'status': 'open', 'claim_reference': 'sample', 'evidence_ref': 'sample', 'preparer_id': 'sample', 'certifier_id': 'sample', 'decision': 'sample', 'claim_amount': 1.5, 'retention_amount': 1.5, 'net_certified': 1.5})
    if not isinstance(out, dict):
        failures.append('claim_evidence_and_approvals returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('claim_evidence_and_approvals')
    elif out.get('ok') is False:
        failures.append('claim_evidence_and_approvals rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('claim_evidence_and_approvals')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('claim_evidence_and_approvals reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('claim_evidence_and_approvals')
    assert not failures, "; ".join(failures)
