"""Email capability.

The vendored email block validates the address and sends through the provider
the deployment configured (SendGrid, SES or SMTP).  The capability passes the
operator's environment settings to the block; with no provider configured it
reports `unconfigured` and names the settings, never `delivered: true`.

SCALE: one message per call.
READS: caller fields; SMTP/SendGrid settings from the deployment.
WRITES: the delivery record in the response; the route persists the record.
NEVER: a send acknowledgement the block did not return.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from app import domain_rules
from app.action_common import block_failed, fail, ok, refusal_text
from app.dispatch import execute, execute_sequence

CAPABILITY_ID = "email"
ENTITY = "email"
BLOCK_IDS = ["email"]
BLOCK_DEFAULT_ACTIONS = {"email": "send"}
AUTHORED_BY = "codewhale exec"


def _config() -> Dict[str, Any]:
    sendgrid_key = (os.getenv("SENDGRID_API_KEY") or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    explicit = (os.getenv("EMAIL_PROVIDER") or "").strip().lower()
    if explicit in {"sendgrid", "ses", "smtp"}:
        provider = explicit
    elif sendgrid_key:
        provider = "sendgrid"
    elif smtp_host:
        provider = "smtp"
    else:
        provider = ""
    port = (os.getenv("SMTP_PORT") or "").strip()
    return {
        "provider": provider or "sendgrid",
        "sendgrid_key": sendgrid_key,
        "ses_key": (os.getenv("SES_KEY") or "").strip(),
        "from_email": (os.getenv("DEFAULT_FROM_EMAIL") or "noreply@localhost").strip(),
        "smtp_host": smtp_host or None,
        "smtp_port": int(port) if port.isdigit() else 587,
        "smtp_user": (os.getenv("SMTP_USER") or "").strip(),
        "smtp_pass": (os.getenv("SMTP_PASS") or "").strip(),
    }


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    recipient = str(data.get("recipient_email") or "").strip()
    subject = str(data.get("subject") or "Delivery Service Platform").strip()
    body = str(data.get("body") or data.get("notes") or "")

    config = _config()
    configured = bool(
        (config["smtp_host"] and config["provider"] == "smtp")
        or config.get("sendgrid_key")
        or config.get("ses_key")
    )

    validation = execute("email", {"email": recipient}, action="validate_address")
    if block_failed(validation):
        return fail(refusal_text(validation))

    outcome: Dict[str, Any] = {}
    if configured:
        outcome = execute_sequence(
            "email",
            [{"action": BLOCK_DEFAULT_ACTIONS.get("email"),
              "input": {"to": recipient, "subject": subject, "body": body}}],
            config=config,
        )
        if block_failed(outcome):
            return fail(refusal_text(outcome))

    valid = validation.get("valid")
    delivered = bool(outcome.get("sent")) if configured else False
    domain = recipient.split("@", 1)[1].casefold() if "@" in recipient else None
    return ok({
        "recipient_email": recipient,
        "recipient_domain": domain,
        "subject": subject,
        "subject_length": len(subject),
        "body_length": len(body),
        "body_words": len(body.split()),
        "valid": valid,
        "provider": config["provider"] if configured else None,
        "delivered": delivered,
        "delivery": "sent" if delivered else "unconfigured",
        "setting": None if configured else "SMTP_HOST or SENDGRID_API_KEY or EMAIL_PROVIDER",
        "message_digest": domain_rules.canonical_digest(
            {"to": recipient, "subject": subject, "body": body}
        ),
    })
