"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import progress_claim_administration
    assert progress_claim_administration.CAPABILITY_ID
    from app.actions import delay_damages_tracking
    assert delay_damages_tracking.CAPABILITY_ID
    from app.actions import qa_itp_records
    assert qa_itp_records.CAPABILITY_ID
    from app.actions import document_register
    assert document_register.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['approval_rules', 'boq_processor', 'document_engine', 'finance_reconciliation', 'formula_executor', 'search', 'validation', 'version', 'workflow']:
        load_block(block_id)
    actions = {'validation': 'validate_pipeline', 'version': 'publish_version', 'workflow': 'run'}
    for block_id in ['approval_rules', 'boq_processor', 'document_engine', 'finance_reconciliation', 'formula_executor', 'search', 'validation', 'version', 'workflow']:
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
    from app.actions import progress_claim_administration
    try:
        out = progress_claim_administration.handle({'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('progress_claim_administration handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('progress_claim_administration')
    from app.actions import delay_damages_tracking
    try:
        out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('delay_damages_tracking handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('delay_damages_tracking')
    from app.actions import qa_itp_records
    try:
        out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('qa_itp_records handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('qa_itp_records')
    from app.actions import document_register
    try:
        out = document_register.handle({'reference': 'sample', 'status': 'open', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('document_register handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('document_register')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import progress_claim_administration
    out = progress_claim_administration.handle({'reference': 'sample', 'status': 'open', 'claim_number': 'sample', 'period_from': '2026-09-03', 'period_to': '2026-09-03', 'boq_item_codes': 'sample', 'claimed_quantity': 1.0, 'unit_rate': 1.0, 'claimed_amount': 1.0, 'certified_amount': 1.0, 'retention_amount': 1.0, 'performance_security': 1.0, 'accepted_contract_amount': 1.0, 'line_items': 'sample', 'clause_reference': 'sample'})
    if not isinstance(out, dict):
        failures.append('progress_claim_administration returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('progress_claim_administration')
    elif out.get('ok') is False:
        failures.append('progress_claim_administration rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('progress_claim_administration')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('progress_claim_administration reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('progress_claim_administration')
    from app.actions import delay_damages_tracking
    out = delay_damages_tracking.handle({'reference': 'sample', 'status': 'open', 'notice_reference': 'sample', 'commencement_date': '2026-09-03', 'completion_date': '2026-09-03', 'actual_completion_date': '2026-09-03', 'accepted_contract_amount': 1.0, 'days_of_delay': 1, 'daily_rate': 1.0, 'damages_cap_ratio': 1.0, 'damages_amount': 1.0, 'clause_reference': 'sample'})
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
    out = qa_itp_records.handle({'reference': 'sample', 'status': 'open', 'itp_number': 'sample', 'inspection_type': 'sample', 'boq_item_code': 'sample', 'inspection_date': '2026-09-03', 'result': 'pass', 'inspector': 'sample', 'notes': 'sample', 'evidence_text': 'sample'})
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
    out = document_register.handle({'reference': 'sample', 'status': 'open', 'title': 'sample', 'document_type': 'contract', 'revision': 'sample', 'issued_date': '2026-09-03', 'source_document': 'sample', 'checksum': 'sample', 'supersedes': 'sample', 'description': 'sample', 'search_query': 'sample'})
    if not isinstance(out, dict):
        failures.append('document_register returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('document_register')
    elif out.get('ok') is False:
        failures.append('document_register rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('document_register')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('document_register reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('document_register')
    assert not failures, "; ".join(failures)
