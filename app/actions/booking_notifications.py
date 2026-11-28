"""Booking notifications to the contractor and the customer.

Every lifecycle change produces a typed message: a new request alerts the
contractor, a confirmation or a later state goes to the customer.  Email and
webhook delivery are the vendored notification block's live channels; when no
channel is configured the capability says so and reports the exact setting,
rather than pretending a message left the process.  SMS is a declared
placeholder because the customer named no SMS provider.

SCALE: one recipient message per call.
READS: caller fields and the deployment's channel settings.
WRITES: the delivery record in the response; the route persists the record.
NEVER: a `delivered: true` without the block's own sent acknowledgement.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute

CAPABILITY_ID = "booking_notifications"
ENTITY = "booking_notifications"
BLOCK_IDS = ["notification"]
BLOCK_DEFAULT_ACTIONS = {"notification": "send"}
AUTHORED_BY = "codewhale exec"

SMS_SETTING = "SMS_GATEWAY_PROVIDER_NOT_SPECIFIED_BY_THE_USER_SHIPS_AS_A_MARKED_PLACEHOLDER_CREDENTIALS"

REQUEST_EVENTS = {"requested", "booking_requested", "new", "created"}
CONFIRM_EVENTS = {"accepted", "confirmed", "in_progress", "completed", "cancelled"}


def _audience(event: str) -> str:
    text = str(event or "").casefold()
    if text in REQUEST_EVENTS:
        return "contractor"
    if text in CONFIRM_EVENTS:
        return "customer"
    return "both"


def _phase(event: str) -> str:
    text = str(event or "").casefold()
    if text in REQUEST_EVENTS:
        return "request"
    if text in CONFIRM_EVENTS:
        return "lifecycle_change"
    return "notice"


def _email_ready() -> bool:
    return bool(
        (os.getenv("SMTP_HOST") or "").strip()
        or (os.getenv("SMTP_URL") or "").strip()
        or (os.getenv("SENDGRID_API_KEY") or "").strip()
    )


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    reference = str(data.get("reference") or "notification")
    booking = str(data.get("booking_reference") or reference)
    event = str(data.get("event_type") or "booking_requested")
    channel = str(data.get("channel") or "email").casefold()
    recipient = str(data.get("recipient_email") or data.get("recipient_phone") or "").strip()
    message = str(data.get("message") or "").strip()
    audience = _audience(event)

    if channel == "sms":
        return fail(
            "SMS delivery needs a provider the customer did not name",
            error_kind="unavailable",
            settings=[SMS_SETTING],
            connector="sms_gateway_provider_not_specified_by_the_user_ships_as_a_marked_placeholder",
        )
    if channel not in {"email", "webhook"}:
        return fail("channel must be email or webhook", error_kind="validation_error",
                    rejected_field="channel")
    if channel == "email":
        if not recipient:
            return fail("recipient_email is required for email delivery",
                        error_kind="validation_error", rejected_field="recipient_email")
        if "@" not in recipient:
            return fail("recipient_email is not a valid address",
                        error_kind="validation_error", rejected_field="recipient_email")

    if not message:
        message = "Booking %s: %s" % (booking, event.replace("_", " "))

    if channel == "email" and not _email_ready():
        health = execute("notification", {}, action="health")
        status = "unconfigured"
        setting = "SMTP_HOST or SENDGRID_API_KEY or SMTP_URL"
        delivered = False
        message_id = None
        block_state = health.get("status") or health.get("state") or "unknown"
    else:
        delivery = execute(
            "notification",
            {
                "channel": channel,
                "to": recipient,
                "subject": "Booking %s %s" % (booking, event.replace("_", " ")),
                "message": message,
                "event": "booking.%s" % event,
                "payload": {
                    "booking_reference": booking,
                    "event_type": event,
                    "audience": audience,
                    "reference": reference,
                },
            },
            action=BLOCK_DEFAULT_ACTIONS.get("notification"),
        )
        if block_failed(delivery):
            return fail(refusal_text(delivery))
        delivered = bool(delivery.get("sent"))
        message_id = delivery.get("message_id")
        status = "sent" if delivered else (delivery.get("status") or "unavailable")
        setting = None if delivered else "NOTIFY_WEBHOOK_URL or SMTP_HOST"
        block_state = delivery.get("status")

    domain = recipient.split("@", 1)[1].casefold() if "@" in recipient else None
    return ok({
        "booking_reference": booking,
        "event_type": event,
        "audience": audience,
        "event_phase": _phase(event),
        "channel": channel,
        "recipient": recipient or None,
        "recipient_domain": domain,
        "delivered": delivered,
        "delivery": status,
        "message_id": message_id,
        "setting": setting,
        "message_length": len(message),
        "message_words": len(message.split()),
        "block_state": block_state,
        "message_digest": domain_rules.canonical_digest({
            "to": recipient, "event": event, "message": message,
        }),
    })
