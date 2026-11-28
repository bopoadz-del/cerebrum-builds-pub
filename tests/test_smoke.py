"""The platform runs, and it runs without the store."""
TESTER_PROMPT = "{\"ask\": \"A delivery-service marketplace platform where the operator employs subcontractor drivers/contractors. Contractors get their own accounts to manage their schedule and availability, and choose the active suburb locations they are willing to work in. Customers browse available contractors by location (suburb) and availability, and book them into time slots. Core needs: contractor onboarding and profiles with per-suburb service areas; contractor availability/schedule calendar management; customer-facing booking flow filtered by suburb and availability with double-booking prevention; location-based matching of bookings to contractors who have selected that suburb as active; notifications to contractor on new booking and confirmation to the customer; booking status lifecycle (requested, accepted, in progress, completed, cancelled); an admin/ops back office to oversee contractors, suburbs, bookings and disputes; and money handling for customer invoicing and subcontractor payouts. Country and currency were not specified by the user and must not be assumed \u2014 tax, VAT and payout rules depend on them, so the blueprint must leave them as explicit open parameters (with country/currency configurable) rather than guessing. Build level also not chosen by the user; ask the user to pick prototype/light/pilot/production before the build starts. Scale in the first year was not stated. Outside systems in use (accounting, payments, email/SMS, calendars) were not stated.\\n\\nIn the user's own words:\\n- I need a delivery service platform where I can employ subcontractors where they can manage their schedules availability and then customer can book them based on locations and availability. The contractors has to choose active suburb locations they want to work in\\n- Start\", \"documents\": {\"file_types\": [], \"uploads\": false}}"

import os

import pytest


def test_capabilities_import():
    from app.actions import customer_booking_flow
    assert customer_booking_flow.CAPABILITY_ID
    from app.actions import contractor_onboarding_and_service_areas
    assert contractor_onboarding_and_service_areas.CAPABILITY_ID
    from app.actions import contractor_availability_schedule
    assert contractor_availability_schedule.CAPABILITY_ID
    from app.actions import location_based_matching
    assert location_based_matching.CAPABILITY_ID
    from app.actions import booking_status_lifecycle
    assert booking_status_lifecycle.CAPABILITY_ID
    from app.actions import booking_notifications
    assert booking_notifications.CAPABILITY_ID
    from app.actions import invoicing_and_payouts
    assert invoicing_and_payouts.CAPABILITY_ID
    from app.actions import ops_back_office
    assert ops_back_office.CAPABILITY_ID
    from app.actions import audit
    assert audit.CAPABILITY_ID
    from app.actions import config
    assert config.CAPABILITY_ID
    from app.actions import email
    assert email.CAPABILITY_ID
    from app.actions import billing
    assert billing.CAPABILITY_ID


def test_dispatch_runs_offline():
    """No store env, no network: every block must LOAD and EXECUTE from
    vendor/. A block-level refusal of this bare probe is still local
    execution; an import failure is the store dependency this test
    exists to catch."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY", "CEREBRUM_API_TOKEN"):
        os.environ.pop(var, None)
    from app.dispatch import execute, load_block
    for block_id in ['audit', 'billing', 'config', 'dashboard', 'dispatch_matching', 'dispute_resolution', 'email', 'notification', 'payment_escrow', 'task_listing', 'transaction_state_machine', 'vendor_catalog']:
        load_block(block_id)
    actions = {'audit': 'log', 'billing': 'record_usage', 'config': 'get', 'dashboard': 'render', 'email': 'send', 'notification': 'send'}
    for block_id in ['audit', 'billing', 'config', 'dashboard', 'dispatch_matching', 'dispute_resolution', 'email', 'notification', 'payment_escrow', 'task_listing', 'transaction_state_machine', 'vendor_catalog']:
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
    from app.actions import customer_booking_flow
    try:
        out = customer_booking_flow.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'customer_name': 'sample', 'customer_email': 'guest@example.com', 'contractor_reference': 'sample', 'suburb': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'end_time': '10:00:00', 'service_type': 'sample', 'quoted_amount': 1.0, 'cost_amount': 1.0})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('customer_booking_flow handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('customer_booking_flow')
    from app.actions import contractor_onboarding_and_service_areas
    try:
        out = contractor_onboarding_and_service_areas.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_name': 'sample', 'contact_email': 'guest@example.com', 'phone': 'sample', 'service_suburbs': 'sample', 'pending_suburbs': 'sample', 'catalogue_state': 'sample', 'vehicle_type': 'sample', 'capacity': 1, 'active': True})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('contractor_onboarding_and_service_areas handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('contractor_onboarding_and_service_areas')
    from app.actions import contractor_availability_schedule
    try:
        out = contractor_availability_schedule.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_reference': 'sample', 'weekday': 'monday', 'start_time': '10:00:00', 'end_time': '10:00:00', 'capacity': 1, 'active': True})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('contractor_availability_schedule handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('contractor_availability_schedule')
    from app.actions import location_based_matching
    try:
        out = location_based_matching.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'suburb': 'sample', 'contractor_reference': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'distance_km': 1.0, 'required_skills': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('location_based_matching handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('location_based_matching')
    from app.actions import booking_status_lifecycle
    try:
        out = booking_status_lifecycle.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'current_state': 'requested', 'target_state': 'requested', 'actor': 'customer', 'transition_id': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('booking_status_lifecycle handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('booking_status_lifecycle')
    from app.actions import booking_notifications
    try:
        out = booking_notifications.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'recipient_email': 'guest@example.com', 'recipient_phone': 'sample', 'channel': 'email', 'message': 'sample', 'event_type': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('booking_notifications handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('booking_notifications')
    from app.actions import invoicing_and_payouts
    try:
        out = invoicing_and_payouts.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'amount': 1.0, 'units': 1.0, 'payee_reference': 'sample', 'invoice_reference': 'sample', 'payout_stage': 'hold', 'released_amount': 1.0})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('invoicing_and_payouts handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('invoicing_and_payouts')
    from app.actions import ops_back_office
    try:
        out = ops_back_office.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'dispute_reference': 'sample', 'booking_reference': 'sample', 'claimant': 'sample', 'claim_type': 'sample', 'suburb': 'sample', 'region': 'sample', 'resolution_notes': 'sample', 'dispute_action': 'open', 'resolution': 'released', 'maintain_suburbs': True, 'suburb_active': True})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('ops_back_office handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('ops_back_office')
    from app.actions import audit
    try:
        out = audit.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'event': 'sample', 'resource_type': 'sample', 'resource_id': 'sample', 'details': 'sample', 'actor': 'sample', 'sequence': 1, 'previous_digest': 'sample', 'chain_digest': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('audit handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('audit')
    from app.actions import config
    try:
        out = config.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'config_block': 'sample', 'key': 'sample', 'value': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('config handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('config')
    from app.actions import email
    try:
        out = email.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'recipient_email': 'guest@example.com', 'subject': 'sample', 'body': 'sample'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('email handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('email')
    from app.actions import billing
    try:
        out = billing.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'api_key': 'sample', 'block_used': 'sample', 'tokens': 1, 'plan': 'free'})
    except Exception as exc:
        out = {'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)}
    if not isinstance(out, dict):
        failures.append('billing handle() must return a dict, got ' + type(out).__name__)
        _record_capability_failure('billing')
    assert not failures, "; ".join(failures)


@pytest.mark.pilot
def test_every_capability_executes_end_to_end():
    """Pilot: each handler runs its blocks on a spec payload and
    Store must accept it. Not the factory code-phase gate."""
    for var in ("CEREBRUM_API_URL", "CEREBRUM_API_KEY"):
        os.environ.pop(var, None)
    import json as _json
    failures = []
    from app.actions import customer_booking_flow
    out = customer_booking_flow.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'customer_name': 'sample', 'customer_email': 'guest@example.com', 'contractor_reference': 'sample', 'suburb': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'end_time': '10:00:00', 'service_type': 'sample', 'quoted_amount': 1.0, 'cost_amount': 1.0})
    if not isinstance(out, dict):
        failures.append('customer_booking_flow returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('customer_booking_flow')
    elif out.get('ok') is False:
        failures.append('customer_booking_flow rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('customer_booking_flow')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('customer_booking_flow reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('customer_booking_flow')
    from app.actions import contractor_onboarding_and_service_areas
    out = contractor_onboarding_and_service_areas.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_name': 'sample', 'contact_email': 'guest@example.com', 'phone': 'sample', 'service_suburbs': 'sample', 'pending_suburbs': 'sample', 'catalogue_state': 'sample', 'vehicle_type': 'sample', 'capacity': 1, 'active': True})
    if not isinstance(out, dict):
        failures.append('contractor_onboarding_and_service_areas returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('contractor_onboarding_and_service_areas')
    elif out.get('ok') is False:
        failures.append('contractor_onboarding_and_service_areas rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('contractor_onboarding_and_service_areas')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('contractor_onboarding_and_service_areas reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('contractor_onboarding_and_service_areas')
    from app.actions import contractor_availability_schedule
    out = contractor_availability_schedule.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'contractor_reference': 'sample', 'weekday': 'monday', 'start_time': '10:00:00', 'end_time': '10:00:00', 'capacity': 1, 'active': True})
    if not isinstance(out, dict):
        failures.append('contractor_availability_schedule returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('contractor_availability_schedule')
    elif out.get('ok') is False:
        failures.append('contractor_availability_schedule rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('contractor_availability_schedule')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('contractor_availability_schedule reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('contractor_availability_schedule')
    from app.actions import location_based_matching
    out = location_based_matching.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'suburb': 'sample', 'contractor_reference': 'sample', 'booking_date': '2026-09-03', 'start_time': '10:00:00', 'distance_km': 1.0, 'required_skills': 'sample'})
    if not isinstance(out, dict):
        failures.append('location_based_matching returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('location_based_matching')
    elif out.get('ok') is False:
        failures.append('location_based_matching rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('location_based_matching')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('location_based_matching reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('location_based_matching')
    from app.actions import booking_status_lifecycle
    out = booking_status_lifecycle.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'current_state': 'requested', 'target_state': 'requested', 'actor': 'customer', 'transition_id': 'sample'})
    if not isinstance(out, dict):
        failures.append('booking_status_lifecycle returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('booking_status_lifecycle')
    elif out.get('ok') is False:
        failures.append('booking_status_lifecycle rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('booking_status_lifecycle')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('booking_status_lifecycle reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('booking_status_lifecycle')
    from app.actions import booking_notifications
    out = booking_notifications.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'recipient_email': 'guest@example.com', 'recipient_phone': 'sample', 'channel': 'email', 'message': 'sample', 'event_type': 'sample'})
    if not isinstance(out, dict):
        failures.append('booking_notifications returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('booking_notifications')
    elif out.get('ok') is False:
        failures.append('booking_notifications rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('booking_notifications')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('booking_notifications reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('booking_notifications')
    from app.actions import invoicing_and_payouts
    out = invoicing_and_payouts.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'booking_reference': 'sample', 'amount': 1.0, 'units': 1.0, 'payee_reference': 'sample', 'invoice_reference': 'sample', 'payout_stage': 'hold', 'released_amount': 1.0})
    if not isinstance(out, dict):
        failures.append('invoicing_and_payouts returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('invoicing_and_payouts')
    elif out.get('ok') is False:
        failures.append('invoicing_and_payouts rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('invoicing_and_payouts')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('invoicing_and_payouts reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('invoicing_and_payouts')
    from app.actions import ops_back_office
    out = ops_back_office.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'dispute_reference': 'sample', 'booking_reference': 'sample', 'claimant': 'sample', 'claim_type': 'sample', 'suburb': 'sample', 'region': 'sample', 'resolution_notes': 'sample', 'dispute_action': 'open', 'resolution': 'released', 'maintain_suburbs': True, 'suburb_active': True})
    if not isinstance(out, dict):
        failures.append('ops_back_office returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('ops_back_office')
    elif out.get('ok') is False:
        failures.append('ops_back_office rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('ops_back_office')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('ops_back_office reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('ops_back_office')
    from app.actions import audit
    out = audit.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'event': 'sample', 'resource_type': 'sample', 'resource_id': 'sample', 'details': 'sample', 'actor': 'sample', 'sequence': 1, 'previous_digest': 'sample', 'chain_digest': 'sample'})
    if not isinstance(out, dict):
        failures.append('audit returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('audit')
    elif out.get('ok') is False:
        failures.append('audit rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('audit')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('audit reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('audit')
    from app.actions import config
    out = config.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'config_block': 'sample', 'key': 'sample', 'value': 'sample'})
    if not isinstance(out, dict):
        failures.append('config returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('config')
    elif out.get('ok') is False:
        failures.append('config rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('config')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('config reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('config')
    from app.actions import email
    out = email.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'recipient_email': 'guest@example.com', 'subject': 'sample', 'body': 'sample'})
    if not isinstance(out, dict):
        failures.append('email returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('email')
    elif out.get('ok') is False:
        failures.append('email rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('email')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('email reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('email')
    from app.actions import billing
    out = billing.handle({'reference': 'sample', 'status': 'open', 'notes': 'sample', 'api_key': 'sample', 'block_used': 'sample', 'tokens': 1, 'plan': 'free'})
    if not isinstance(out, dict):
        failures.append('billing returned a non-dict: ' + repr(out)[:120])
        _record_capability_failure('billing')
    elif out.get('ok') is False:
        failures.append('billing rejected a payload built from its own schema: ' + str(out.get('error')))
        _record_capability_failure('billing')
    elif '\"status\": \"error\"' in _json.dumps(out, default=str) or '\"status\": \"failed\"' in _json.dumps(out, default=str):
        failures.append('billing reported ok around a failed block call: ' + _json.dumps(out, default=str)[:300])
        _record_capability_failure('billing')
    assert not failures, "; ".join(failures)
