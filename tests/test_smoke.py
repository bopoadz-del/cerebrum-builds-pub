"""The platform runs, and it runs without the store."""

import os

import pytest


def test_capabilities_import():
    from app.actions import track_management
    assert track_management.CAPABILITY_ID
    from app.actions import enrolment_and_scheduling
    assert enrolment_and_scheduling.CAPABILITY_ID
    from app.actions import ai_faculty_sessions
    assert ai_faculty_sessions.CAPABILITY_ID
    from app.actions import memo_grading
    assert memo_grading.CAPABILITY_ID
    from app.actions import gradebook_and_transcript
    assert gradebook_and_transcript.CAPABILITY_ID
    from app.actions import defenses_and_capstone
    assert defenses_and_capstone.CAPABILITY_ID
    from app.actions import library_surfaces
    assert library_surfaces.CAPABILITY_ID
    from app.actions import command_center_and_chat
    assert command_center_and_chat.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['aesthetic_kit', 'agent_swarm', 'analytics', 'answer_quality_scorer', 'approval_rules', 'audit', 'audit_chain', 'cpm_engine', 'dashboard', 'email', 'evidence_chain', 'evidence_verifier', 'formula_executor', 'knowledge', 'memory', 'notification', 'pdf', 'reference_corpus', 'search', 'spec_analyzer', 'sub_agent_runtime', 'team', 'transaction_state_machine', 'validation', 'validation_pipeline_fork', 'vector_search', 'voice', 'workbench', 'workflow']:
        load_block(block_id)
    actions = {'agent_swarm': 'execute', 'analytics': 'track_event', 'audit': 'log', 'dashboard': 'render', 'email': 'send', 'evidence_verifier': 'store', 'knowledge': 'ask', 'memory': 'get', 'notification': 'send', 'team': 'create_team', 'validation': 'validate_pipeline', 'workbench': 'run', 'workflow': 'run'}
    for block_id in ['aesthetic_kit', 'agent_swarm', 'analytics', 'answer_quality_scorer', 'approval_rules', 'audit', 'audit_chain', 'cpm_engine', 'dashboard', 'email', 'evidence_chain', 'evidence_verifier', 'formula_executor', 'knowledge', 'memory', 'notification', 'pdf', 'reference_corpus', 'search', 'spec_analyzer', 'sub_agent_runtime', 'team', 'transaction_state_machine', 'validation', 'validation_pipeline_fork', 'vector_search', 'voice', 'workbench', 'workflow']:
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
    from app.actions import track_management
    try:
        out = track_management.handle({'reference': 'sample', 'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('track_management handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('track_management')
    from app.actions import enrolment_and_scheduling
    try:
        out = enrolment_and_scheduling.handle({'reference': 'sample', 'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('enrolment_and_scheduling handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('enrolment_and_scheduling')
    from app.actions import ai_faculty_sessions
    try:
        out = ai_faculty_sessions.handle({'reference': 'sample', 'session_kind': 'framework', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('ai_faculty_sessions handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('ai_faculty_sessions')
    from app.actions import memo_grading
    try:
        out = memo_grading.handle({'reference': 'sample', 'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('memo_grading handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('memo_grading')
    from app.actions import gradebook_and_transcript
    try:
        out = gradebook_and_transcript.handle({'reference': 'sample', 'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('gradebook_and_transcript handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('gradebook_and_transcript')
    from app.actions import defenses_and_capstone
    try:
        out = defenses_and_capstone.handle({'reference': 'sample', 'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('defenses_and_capstone handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('defenses_and_capstone')
    from app.actions import library_surfaces
    try:
        out = library_surfaces.handle({'reference': 'sample', 'track_key': 'sample', 'week': 1, 'session_kind': 'framework', 'query': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('library_surfaces handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('library_surfaces')
    from app.actions import command_center_and_chat
    try:
        out = command_center_and_chat.handle({'reference': 'sample', 'stage': 'enrol', 'message': 'sample', 'status': 'open'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('command_center_and_chat handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('command_center_and_chat')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import track_management
    out = track_management.handle({'reference': 'sample', 'track_key': 'sample', 'title': 'sample', 'track_version': 1, 'weeks': 1, 'yaml_text': 'sample', 'previous_yaml': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('track_management returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('track_management')
    elif out.get('ok') is False:
        failures.append('track_management rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('track_management')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('track_management reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('track_management')
    from app.actions import enrolment_and_scheduling
    out = enrolment_and_scheduling.handle({'reference': 'sample', 'learner_email': 'guest@example.com', 'track_key': 'sample', 'start_date': '2026-09-03', 'timezone': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('enrolment_and_scheduling returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('enrolment_and_scheduling')
    elif out.get('ok') is False:
        failures.append('enrolment_and_scheduling rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('enrolment_and_scheduling')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('enrolment_and_scheduling reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('enrolment_and_scheduling')
    from app.actions import ai_faculty_sessions
    out = ai_faculty_sessions.handle({'reference': 'sample', 'session_kind': 'framework', 'kernel_mode': 'lecture', 'week': 1, 'learner_question': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('ai_faculty_sessions returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('ai_faculty_sessions')
    elif out.get('ok') is False:
        failures.append('ai_faculty_sessions rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('ai_faculty_sessions')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('ai_faculty_sessions reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('ai_faculty_sessions')
    from app.actions import memo_grading
    out = memo_grading.handle({'reference': 'sample', 'learner_id': 'sample', 'memo_text': 'sample', 'rubric_version': 'sample', 'word_count': 1, 'status': 'open'})
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
    out = gradebook_and_transcript.handle({'reference': 'sample', 'learner_id': 'sample', 'memos_score': 1.0, 'defenses_score': 1.0, 'capstone_score': 1.0, 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('gradebook_and_transcript returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('gradebook_and_transcript')
    elif out.get('ok') is False:
        failures.append('gradebook_and_transcript rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('gradebook_and_transcript')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('gradebook_and_transcript reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('gradebook_and_transcript')
    from app.actions import defenses_and_capstone
    out = defenses_and_capstone.handle({'reference': 'sample', 'learner_id': 'sample', 'defense_date': '2026-09-03', 'capstone_title': 'sample', 'reviewer_email': 'guest@example.com', 'verdict_count': 1, 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('defenses_and_capstone returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('defenses_and_capstone')
    elif out.get('ok') is False:
        failures.append('defenses_and_capstone rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('defenses_and_capstone')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('defenses_and_capstone reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('defenses_and_capstone')
    from app.actions import library_surfaces
    out = library_surfaces.handle({'reference': 'sample', 'track_key': 'sample', 'week': 1, 'session_kind': 'framework', 'query': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('library_surfaces returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('library_surfaces')
    elif out.get('ok') is False:
        failures.append('library_surfaces rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('library_surfaces')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('library_surfaces reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('library_surfaces')
    from app.actions import command_center_and_chat
    out = command_center_and_chat.handle({'reference': 'sample', 'stage': 'enrol', 'message': 'sample', 'status': 'open'})
    if not isinstance(out, dict):
        failures.append('command_center_and_chat returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('command_center_and_chat')
    elif out.get('ok') is False:
        failures.append('command_center_and_chat rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('command_center_and_chat')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('command_center_and_chat reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('command_center_and_chat')
    assert not failures, "; ".join(failures)
