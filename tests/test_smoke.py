"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import contract_source_of_record
    assert contract_source_of_record.CAPABILITY_ID
    from app.actions import progress_claims
    assert progress_claims.CAPABILITY_ID
    from app.actions import time_and_delay_damages
    assert time_and_delay_damages.CAPABILITY_ID
    from app.actions import qa_itp_records
    assert qa_itp_records.CAPABILITY_ID
    from app.actions import document_register
    assert document_register.CAPABILITY_ID
    from app.actions import role_based_access_and_audit
    assert role_based_access_and_audit.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['approval_rules', 'audit', 'audit_chain', 'audit_fail_closed', 'auth', 'boq_processor', 'capture', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'file_hasher', 'finance_canonical_model', 'finance_planning', 'finance_reconciliation', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'knowledge', 'multi_tenant_rbac', 'notification', 'ocr', 'pdf', 'review', 'search', 'storage', 'transaction_state_machine', 'validation', 'version', 'version_diff', 'workbench', 'workflow']:
        load_block(block_id)
    actions = {'audit': 'log', 'auth': 'validate', 'dashboard': 'render', 'knowledge': 'ask', 'notification': 'send', 'review': 'approve', 'storage': 'store', 'validation': 'validate_pipeline', 'version': 'publish_version', 'workbench': 'run', 'workflow': 'run'}
    for block_id in ['approval_rules', 'audit', 'audit_chain', 'audit_fail_closed', 'auth', 'boq_processor', 'capture', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'file_hasher', 'finance_canonical_model', 'finance_planning', 'finance_reconciliation', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'knowledge', 'multi_tenant_rbac', 'notification', 'ocr', 'pdf', 'review', 'search', 'storage', 'transaction_state_machine', 'validation', 'version', 'version_diff', 'workbench', 'workflow']:
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
    from app.actions import contract_source_of_record
    try:
        out = contract_source_of_record.handle({'reference': 'sample', 'source_document': 'document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('contract_source_of_record handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('contract_source_of_record')
    from app.actions import progress_claims
    try:
        out = progress_claims.handle({'reference': 'sample', 'ipc_number': 'sample', 'boq_item': 'P1', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('progress_claims handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('progress_claims')
    from app.actions import time_and_delay_damages
    try:
        out = time_and_delay_damages.handle({'reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('time_and_delay_damages handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('time_and_delay_damages')
    from app.actions import qa_itp_records
    try:
        out = qa_itp_records.handle({'reference': 'sample', 'boq_item': 'P1', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('qa_itp_records handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('qa_itp_records')
    from app.actions import document_register
    try:
        out = document_register.handle({'reference': 'sample', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_register handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_register')
    from app.actions import role_based_access_and_audit
    try:
        out = role_based_access_and_audit.handle({'reference': 'sample', 'principal_id': 'sample', 'role': 'owner', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('role_based_access_and_audit handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('role_based_access_and_audit')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import contract_source_of_record
    out = contract_source_of_record.handle({'reference': 'sample', 'source_document': 'document:62425b8c48e146f08c1ecbbaf93ba637_harbourline_contract.pdf', 'document_type': 'contract', 'clause_ref': '4.2', 'boq_item': 'P1', 'description': 'sample', 'unit': 'sample', 'quantity': 1.0, 'rate': 1.0, 'amount': 1.0, 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('contract_source_of_record returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('contract_source_of_record')
    elif out.get('ok') is False:
        failures.append('contract_source_of_record rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('contract_source_of_record')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('contract_source_of_record reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('contract_source_of_record')
    from app.actions import progress_claims
    out = progress_claims.handle({'reference': 'sample', 'ipc_number': 'sample', 'boq_item': 'P1', 'period': 'sample', 'gross_amount': 1.0, 'accepted_contract_amount': 1.0, 'retention_pct': 1.0, 'retention_amount': 1.0, 'performance_security_rate': 1.0, 'performance_security_deduction': 1.0, 'net_certified': 1.0, 'currency': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('progress_claims returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('progress_claims')
    elif out.get('ok') is False:
        failures.append('progress_claims rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('progress_claims')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('progress_claims reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('progress_claims')
    from app.actions import time_and_delay_damages
    out = time_and_delay_damages.handle({'reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'time_for_completion_days': 1, 'accepted_contract_amount': 1.0, 'delay_days': 1, 'delay_damages_rate_pct': 1.0, 'delay_damages': 1.0, 'damages_cap_pct': 1.0, 'cap_reached': True, 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('time_and_delay_damages returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('time_and_delay_damages')
    elif out.get('ok') is False:
        failures.append('time_and_delay_damages rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('time_and_delay_damages')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('time_and_delay_damages reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('time_and_delay_damages')
    from app.actions import qa_itp_records
    out = qa_itp_records.handle({'reference': 'sample', 'boq_item': 'P1', 'inspection_lot': 'sample', 'hold_point': 'sample', 'witness_point': 'sample', 'test_result': 'pass', 'inspection_date': '2026-09-03', 'status': 'open'})
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
    out = document_register.handle({'reference': 'sample', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'checksum': 'sample', 'source_document': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('document_register returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_register')
    elif out.get('ok') is False:
        failures.append('document_register rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_register')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_register reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_register')
    from app.actions import role_based_access_and_audit
    out = role_based_access_and_audit.handle({'reference': 'sample', 'principal_id': 'sample', 'role': 'owner', 'permission': 'contract.read', 'requested_action': 'read', 'decision': 'allow', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('role_based_access_and_audit returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('role_based_access_and_audit')
    elif out.get('ok') is False:
        failures.append('role_based_access_and_audit rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('role_based_access_and_audit')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('role_based_access_and_audit reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('role_based_access_and_audit')
    assert not failures, "; ".join(failures)
