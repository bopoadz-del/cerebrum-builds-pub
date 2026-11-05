"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import track_loader
    assert track_loader.CAPABILITY_ID
    from app.actions import enrolment_and_calendar
    assert enrolment_and_calendar.CAPABILITY_ID
    from app.actions import faculty_session
    assert faculty_session.CAPABILITY_ID
    from app.actions import memo_grading
    assert memo_grading.CAPABILITY_ID
    from app.actions import gradebook_and_transcript
    assert gradebook_and_transcript.CAPABILITY_ID
    from app.actions import defense_and_capstone
    assert defense_and_capstone.CAPABILITY_ID
    from app.actions import track_admin
    assert track_admin.CAPABILITY_ID
    from app.actions import reading_and_case_library
    assert reading_and_case_library.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['analytics', 'approval_rules', 'audit', 'auth', 'config', 'dashboard', 'database', 'email', 'evidence_chain', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'knowledge', 'memory', 'notification', 'orchestrator', 'pdf', 'transaction_state_machine', 'validation', 'vector_search', 'version', 'version_diff', 'workbench', 'workflow']:
        load_block(block_id)
    actions = {}
    for block_id in ['analytics', 'approval_rules', 'audit', 'auth', 'config', 'dashboard', 'database', 'email', 'evidence_chain', 'formula_executor', 'governance_gate', 'ingestion_provenance', 'knowledge', 'memory', 'notification', 'orchestrator', 'pdf', 'transaction_state_machine', 'validation', 'vector_search', 'version', 'version_diff', 'workbench', 'workflow']:
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
    from app.actions import track_loader
    try:
        out = track_loader.handle({'reference': 'sample', 'status': 'open', 'schema_version': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('track_loader handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('track_loader')
    from app.actions import enrolment_and_calendar
    try:
        out = enrolment_and_calendar.handle({'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('enrolment_and_calendar handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('enrolment_and_calendar')
    from app.actions import faculty_session
    try:
        out = faculty_session.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('faculty_session handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('faculty_session')
    from app.actions import memo_grading
    try:
        out = memo_grading.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('memo_grading handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('memo_grading')
    from app.actions import gradebook_and_transcript
    try:
        out = gradebook_and_transcript.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('gradebook_and_transcript handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('gradebook_and_transcript')
    from app.actions import defense_and_capstone
    try:
        out = defense_and_capstone.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('defense_and_capstone handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('defense_and_capstone')
    from app.actions import track_admin
    try:
        out = track_admin.handle({'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('track_admin handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('track_admin')
    from app.actions import reading_and_case_library
    try:
        out = reading_and_case_library.handle({'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('reading_and_case_library handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('reading_and_case_library')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import track_loader
    out = track_loader.handle({'reference': 'sample', 'status': 'open', 'schema_version': 'sample'})
    if not isinstance(out, dict):
        failures.append('track_loader returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('track_loader')
    elif out.get('ok') is False:
        failures.append('track_loader rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('track_loader')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('track_loader reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('track_loader')
    from app.actions import enrolment_and_calendar
    out = enrolment_and_calendar.handle({'reference': 'sample', 'status': 'open', 'learner_name': 'sample', 'learner_email': 'sample', 'start_date': 'sample', 'timezone': 'sample', 'track_version': 'sample'})
    if not isinstance(out, dict):
        failures.append('enrolment_and_calendar returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('enrolment_and_calendar')
    elif out.get('ok') is False:
        failures.append('enrolment_and_calendar rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('enrolment_and_calendar')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('enrolment_and_calendar reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('enrolment_and_calendar')
    from app.actions import faculty_session
    out = faculty_session.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'session_offset': 1, 'mode': 'lecture', 'message': 'sample'})
    if not isinstance(out, dict):
        failures.append('faculty_session returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('faculty_session')
    elif out.get('ok') is False:
        failures.append('faculty_session rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('faculty_session')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('faculty_session reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('faculty_session')
    from app.actions import memo_grading
    out = memo_grading.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'week': 1, 'submission': 'sample', 'rubric_version': 'sample'})
    if not isinstance(out, dict):
        failures.append('memo_grading returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('memo_grading')
    elif out.get('ok') is False:
        failures.append('memo_grading rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('memo_grading')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('memo_grading reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('memo_grading')
    from app.actions import gradebook_and_transcript
    out = gradebook_and_transcript.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'prior_average': 'email'})
    if not isinstance(out, dict):
        failures.append('gradebook_and_transcript returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('gradebook_and_transcript')
    elif out.get('ok') is False:
        failures.append('gradebook_and_transcript rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('gradebook_and_transcript')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('gradebook_and_transcript reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('gradebook_and_transcript')
    from app.actions import defense_and_capstone
    out = defense_and_capstone.handle({'reference': 'sample', 'status': 'open', 'learner_email': 'sample', 'term': 1, 'kind': 'defense', 'scheduled_date': 'sample', 'verdict': 'pass', 'reviewer_email': 'sample', 'defense_minutes': 1})
    if not isinstance(out, dict):
        failures.append('defense_and_capstone returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('defense_and_capstone')
    elif out.get('ok') is False:
        failures.append('defense_and_capstone rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('defense_and_capstone')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('defense_and_capstone reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('defense_and_capstone')
    from app.actions import track_admin
    out = track_admin.handle({'reference': 'sample', 'status': 'open', 'operation': 'validate', 'pinned_version': 'sample'})
    if not isinstance(out, dict):
        failures.append('track_admin returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('track_admin')
    elif out.get('ok') is False:
        failures.append('track_admin rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('track_admin')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('track_admin reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('track_admin')
    from app.actions import reading_and_case_library
    out = reading_and_case_library.handle({'reference': 'sample', 'status': 'open', 'week': 1, 'case_id': 'sample', 'learner_email': 'sample', 'session_offset': 1})
    if not isinstance(out, dict):
        failures.append('reading_and_case_library returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('reading_and_case_library')
    elif out.get('ok') is False:
        failures.append('reading_and_case_library rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('reading_and_case_library')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('reading_and_case_library reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('reading_and_case_library')
    assert not failures, "; ".join(failures)
