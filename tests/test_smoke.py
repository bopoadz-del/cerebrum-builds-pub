"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import progress_claim_processing
    assert progress_claim_processing.CAPABILITY_ID
    from app.actions import delay_damages_tracking
    assert delay_damages_tracking.CAPABILITY_ID
    from app.actions import qa_itp_records
    assert qa_itp_records.CAPABILITY_ID
    from app.actions import document_register
    assert document_register.CAPABILITY_ID
    from app.actions import contract_clause_grounding
    assert contract_clause_grounding.CAPABILITY_ID
    from app.actions import performance_security_tracking
    assert performance_security_tracking.CAPABILITY_ID
    from app.actions import compliance_dashboard
    assert compliance_dashboard.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['analytics', 'approval_rules', 'audit_chain', 'boq_processor', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'evidence_or_refuse', 'evidence_verifier', 'file_hasher', 'finance_canonical_model', 'finance_reconciliation_workflow', 'formula_executor', 'knowledge', 'notification', 'review', 'search', 'transaction_state_machine', 'vector_search', 'version_diff', 'workflow']:
        load_block(block_id)
    actions = {}
    for block_id in ['analytics', 'approval_rules', 'audit_chain', 'boq_processor', 'cpm_engine', 'dashboard', 'document_engine', 'evidence_chain', 'evidence_or_refuse', 'evidence_verifier', 'file_hasher', 'finance_canonical_model', 'finance_reconciliation_workflow', 'formula_executor', 'knowledge', 'notification', 'review', 'search', 'transaction_state_machine', 'vector_search', 'version_diff', 'workflow']:
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
    from app.actions import progress_claim_processing
    try:
        out = progress_claim_processing.handle({'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'claim_period': '2026-09-03', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'accepted_contract_amount': 1.0, 'certified_amount': 1.0, 'retention_percent': 1.0, 'retention_amount': 1.0, 'taking_over_date': '2026-09-03', 'defects_end_date': '2026-09-03', 'net_payable': 1.0, 'clause_citation': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('progress_claim_processing handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('progress_claim_processing')
    from app.actions import delay_damages_tracking
    try:
        out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'event_date': '2026-09-03', 'delay_days': 1.0, 'extension_days': 1.0, 'accepted_contract_amount': 1.0, 'delay_damages_amount': 1.0, 'delay_damages_cap': 1.0, 'exposure_ratio': 1.0, 'clause_citation': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('delay_damages_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('delay_damages_tracking')
    from app.actions import qa_itp_records
    try:
        out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'boq_item': 'sample', 'inspection_type': 'sample', 'inspection_date': '2026-09-03', 'result': 'sample', 'hold_point': True, 'document_reference': 'sample', 'pipeline_status': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('qa_itp_records handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('qa_itp_records')
    from app.actions import document_register
    try:
        out = document_register.handle({'reference': 'sample', 'status': 'open', 'document_title': 'sample', 'document_type': 'sample', 'document_revision': 'sample', 'issued_date': '2026-09-03', 'file_name': 'sample', 'sha256': 'sample', 'supersedes': 'sample', 'linked_clause': 'sample', 'audit_hash': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_register handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_register')
    from app.actions import contract_clause_grounding
    try:
        out = contract_clause_grounding.handle({'reference': 'sample', 'status': 'open', 'question': 'sample', 'clause_reference': 'sample', 'document_reference': 'sample', 'authority_layer': 'sample', 'evidence_count': 1, 'answered': True})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('contract_clause_grounding handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('contract_clause_grounding')
    from app.actions import performance_security_tracking
    try:
        out = performance_security_tracking.handle({'reference': 'sample', 'status': 'open', 'security_number': 'sample', 'provider': 'sample', 'issued_date': '2026-09-03', 'expiry_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'required_amount': 1.0, 'secured_amount': 1.0, 'coverage_ratio': 1.0, 'renewal_notice_days': 1.0, 'days_to_expiry': 1, 'clause_citation': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('performance_security_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('performance_security_tracking')
    from app.actions import compliance_dashboard
    try:
        out = compliance_dashboard.handle({'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_open': 1, 'delay_exposure': 1.0, 'itp_completion_ratio': 1.0, 'documents_registered': 1, 'security_valid': True, 'clause_citation': 'sample', 'snapshot': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('compliance_dashboard handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('compliance_dashboard')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import progress_claim_processing
    out = progress_claim_processing.handle({'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'claim_period': '2026-09-03', 'boq_item': 'sample', 'measured_quantity': 1.0, 'boq_rate': 1.0, 'accepted_contract_amount': 1.0, 'certified_amount': 1.0, 'retention_percent': 1.0, 'retention_amount': 1.0, 'taking_over_date': '2026-09-03', 'defects_end_date': '2026-09-03', 'net_payable': 1.0, 'clause_citation': 'sample'})
    if not isinstance(out, dict):
        failures.append('progress_claim_processing returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('progress_claim_processing')
    elif out.get('ok') is False:
        failures.append('progress_claim_processing rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('progress_claim_processing')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('progress_claim_processing reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('progress_claim_processing')
    from app.actions import delay_damages_tracking
    out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'event_date': '2026-09-03', 'delay_days': 1.0, 'extension_days': 1.0, 'accepted_contract_amount': 1.0, 'delay_damages_amount': 1.0, 'delay_damages_cap': 1.0, 'exposure_ratio': 1.0, 'clause_citation': 'sample'})
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
    out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'boq_item': 'sample', 'inspection_type': 'sample', 'inspection_date': '2026-09-03', 'result': 'sample', 'hold_point': True, 'document_reference': 'sample', 'pipeline_status': 'sample'})
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
    out = document_register.handle({'reference': 'sample', 'status': 'open', 'document_title': 'sample', 'document_type': 'sample', 'document_revision': 'sample', 'issued_date': '2026-09-03', 'file_name': 'sample', 'sha256': 'sample', 'supersedes': 'sample', 'linked_clause': 'sample', 'audit_hash': 'sample'})
    if not isinstance(out, dict):
        failures.append('document_register returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_register')
    elif out.get('ok') is False:
        failures.append('document_register rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_register')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_register reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_register')
    from app.actions import contract_clause_grounding
    out = contract_clause_grounding.handle({'reference': 'sample', 'status': 'open', 'question': 'sample', 'clause_reference': 'sample', 'document_reference': 'sample', 'authority_layer': 'sample', 'evidence_count': 1, 'answered': True})
    if not isinstance(out, dict):
        failures.append('contract_clause_grounding returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('contract_clause_grounding')
    elif out.get('ok') is False:
        failures.append('contract_clause_grounding rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('contract_clause_grounding')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('contract_clause_grounding reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('contract_clause_grounding')
    from app.actions import performance_security_tracking
    out = performance_security_tracking.handle({'reference': 'sample', 'status': 'open', 'security_number': 'sample', 'provider': 'sample', 'issued_date': '2026-09-03', 'expiry_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'required_amount': 1.0, 'secured_amount': 1.0, 'coverage_ratio': 1.0, 'renewal_notice_days': 1.0, 'days_to_expiry': 1, 'clause_citation': 'sample'})
    if not isinstance(out, dict):
        failures.append('performance_security_tracking returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('performance_security_tracking')
    elif out.get('ok') is False:
        failures.append('performance_security_tracking rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('performance_security_tracking')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('performance_security_tracking reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('performance_security_tracking')
    from app.actions import compliance_dashboard
    out = compliance_dashboard.handle({'reference': 'sample', 'status': 'open', 'period': 'sample', 'claims_open': 1, 'delay_exposure': 1.0, 'itp_completion_ratio': 1.0, 'documents_registered': 1, 'security_valid': True, 'clause_citation': 'sample', 'snapshot': 'sample'})
    if not isinstance(out, dict):
        failures.append('compliance_dashboard returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('compliance_dashboard')
    elif out.get('ok') is False:
        failures.append('compliance_dashboard rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('compliance_dashboard')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('compliance_dashboard reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('compliance_dashboard')
    assert not failures, "; ".join(failures)
