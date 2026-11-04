"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import document_register
    assert document_register.CAPABILITY_ID
    from app.actions import progress_claims
    assert progress_claims.CAPABILITY_ID
    from app.actions import delay_damages_tracking
    assert delay_damages_tracking.CAPABILITY_ID
    from app.actions import qa_itp_records
    assert qa_itp_records.CAPABILITY_ID
    from app.actions import contract_clause_governance
    assert contract_clause_governance.CAPABILITY_ID
    from app.actions import payment_security_and_retention_ledger
    assert payment_security_and_retention_ledger.CAPABILITY_ID
    from app.actions import claims_analytics_dashboard
    assert claims_analytics_dashboard.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['analytics', 'approval_rules', 'audit', 'audit_chain', 'boq_processor', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'evidence_or_refuse', 'finance_canonical_model', 'finance_planning', 'finance_reconciliation', 'formula_executor', 'governance_gate', 'knowledge', 'pdf', 'portfolio_rollup', 'regulatory_chunker', 'storage', 'transaction_state_machine', 'validation', 'version', 'version_diff', 'workflow']:
        load_block(block_id)
    actions = {}
    for block_id in ['analytics', 'approval_rules', 'audit', 'audit_chain', 'boq_processor', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'evidence_or_refuse', 'finance_canonical_model', 'finance_planning', 'finance_reconciliation', 'formula_executor', 'governance_gate', 'knowledge', 'pdf', 'portfolio_rollup', 'regulatory_chunker', 'storage', 'transaction_state_machine', 'validation', 'version', 'version_diff', 'workflow']:
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
    from app.actions import document_register
    try:
        out = document_register.handle({'reference': 'sample', 'status': 'open', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_register handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_register')
    from app.actions import progress_claims
    try:
        out = progress_claims.handle({'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('progress_claims handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('progress_claims')
    from app.actions import delay_damages_tracking
    try:
        out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('delay_damages_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('delay_damages_tracking')
    from app.actions import qa_itp_records
    try:
        out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('qa_itp_records handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('qa_itp_records')
    from app.actions import contract_clause_governance
    try:
        out = contract_clause_governance.handle({'reference': 'sample', 'status': 'open', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('contract_clause_governance handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('contract_clause_governance')
    from app.actions import payment_security_and_retention_ledger
    try:
        out = payment_security_and_retention_ledger.handle({'reference': 'sample', 'status': 'open', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('payment_security_and_retention_ledger handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('payment_security_and_retention_ledger')
    from app.actions import claims_analytics_dashboard
    try:
        out = claims_analytics_dashboard.handle({'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('claims_analytics_dashboard handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('claims_analytics_dashboard')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import document_register
    out = document_register.handle({'reference': 'sample', 'status': 'open', 'document_type': 'drawing', 'revision': 'sample', 'supersedes': 'sample', 'approval_state': 'pending', 'source_text': 'sample'})
    if not isinstance(out, dict):
        failures.append('document_register returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_register')
    elif out.get('ok') is False:
        failures.append('document_register rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_register')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_register reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_register')
    from app.actions import progress_claims
    out = progress_claims.handle({'reference': 'sample', 'status': 'open', 'ipc_number': 'sample', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'retention_rate': 1.0, 'amount_certified': 1.0, 'retention_held': 1.0, 'approval_state': 'pending', 'source_text': 'sample'})
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
    out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'commencement_date': '2026-09-03', 'delay_days': 1, 'accepted_contract_amount': 1.0, 'delay_damages_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_assessed': 1.0})
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
    out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'inspection_type': 'earthworks', 'boq_item': 'sample', 'outcome': 'pass', 'evidence_digest': 'sample', 'chain_verified': True, 'source_text': 'sample'})
    if not isinstance(out, dict):
        failures.append('qa_itp_records returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('qa_itp_records')
    elif out.get('ok') is False:
        failures.append('qa_itp_records rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('qa_itp_records')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('qa_itp_records reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('qa_itp_records')
    from app.actions import contract_clause_governance
    out = contract_clause_governance.handle({'reference': 'sample', 'status': 'open', 'clause_id': 'sample', 'clause_type': 'delay_damages', 'source_text': 'sample', 'evidence_ref': 'sample', 'governance_state': 'requested'})
    if not isinstance(out, dict):
        failures.append('contract_clause_governance returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('contract_clause_governance')
    elif out.get('ok') is False:
        failures.append('contract_clause_governance rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('contract_clause_governance')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('contract_clause_governance reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('contract_clause_governance')
    from app.actions import payment_security_and_retention_ledger
    out = payment_security_and_retention_ledger.handle({'reference': 'sample', 'status': 'open', 'entry_type': 'performance_security', 'accepted_contract_amount': 1.0, 'performance_security_rate': 1.0, 'retention_rate': 1.0, 'amount_held': 1.0, 'lifecycle_state': 'created'})
    if not isinstance(out, dict):
        failures.append('payment_security_and_retention_ledger returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('payment_security_and_retention_ledger')
    elif out.get('ok') is False:
        failures.append('payment_security_and_retention_ledger rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('payment_security_and_retention_ledger')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('payment_security_and_retention_ledger reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('payment_security_and_retention_ledger')
    from app.actions import claims_analytics_dashboard
    out = claims_analytics_dashboard.handle({'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_count': 1, 'certified_total': 1.0, 'retention_total': 1.0, 'earned_value': 1.0, 'delay_days': 1})
    if not isinstance(out, dict):
        failures.append('claims_analytics_dashboard returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('claims_analytics_dashboard')
    elif out.get('ok') is False:
        failures.append('claims_analytics_dashboard rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('claims_analytics_dashboard')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('claims_analytics_dashboard reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('claims_analytics_dashboard')
    assert not failures, "; ".join(failures)
