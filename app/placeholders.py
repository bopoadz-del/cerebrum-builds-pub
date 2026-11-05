"""Declared placeholder connectors.

Email delivery is the one integration this build declares and does not
build: there is no SMTP relay credential in the package, and inventing one
would mean a capability that claims to have sent a reading email when it has
not. The POST route answers HTTP 503 with ``error_kind: "unavailable"``
naming the connector and the setting it needs, before the handler runs, and
stores nothing. The rest of the capability stays real -- its list route
answers, and its handler is written for the day the connector exists.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

SETTING = "EMAIL_DELIVERY_CREDENTIALS"

PLACEHOLDERS: Dict[str, List[Dict[str, str]]] = {
    "enrolment_and_calendar": [{"connector": "email_delivery", "setting": SETTING}],
    "defense_and_capstone": [{"connector": "email_delivery", "setting": SETTING}],
}


#: Connector-name view used by the Store acceptance resolver.
PLACEHOLDER_CONNECTORS: Dict[str, List[str]] = {
    capability_id: [item["connector"] for item in entries]
    for capability_id, entries in PLACEHOLDERS.items()
}


def settings_for(capability_id: str) -> List[str]:
    return [item["setting"] for item in PLACEHOLDERS.get(str(capability_id), [])]


def refusal_body(capability_id: str) -> Dict[str, Any]:
    entries = PLACEHOLDERS.get(str(capability_id), [])
    return {
        "ok": False,
        "error": "declared placeholder connector is not built in this package",
        "error_kind": "unavailable",
        "capability_id": str(capability_id),
        "connectors": [item["connector"] for item in entries],
        "settings": [item["setting"] for item in entries],
    }


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    if str(capability_id) not in PLACEHOLDERS:
        return False
    if int(status_code) != 503 or not isinstance(body, Mapping):
        return False
    return (
        body.get("ok") is False
        and body.get("error_kind") == "unavailable"
        and list(body.get("settings") or []) == settings_for(capability_id)
    )
