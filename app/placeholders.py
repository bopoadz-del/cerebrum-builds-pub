"""Declared placeholder connectors.

These capabilities call an outside system the customer did not name.  Their
POST route answers the typed unavailable refusal before validation or any
handler work, and stores nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List

SMS_CONNECTOR = "sms_gateway_provider_not_specified_by_the_user_ships_as_a_marked_placeholder"
PAYMENT_CONNECTOR = "payment_processor_not_specified_by_the_user_ships_as_a_marked_placeholder"
ACCOUNTING_CONNECTOR = "accounting_and_tax_vat_system_not_specified_by_the_user_ships_as_a_marked_placeholder"

PLACEHOLDER_CONNECTORS: Dict[str, List[Dict[str, str]]] = {
    "booking_notifications": [
        {"connector": SMS_CONNECTOR, "setting": SMS_CONNECTOR.upper() + "_CREDENTIALS"},
    ],
    "invoicing_and_payouts": [
        {"connector": ACCOUNTING_CONNECTOR, "setting": ACCOUNTING_CONNECTOR.upper() + "_CREDENTIALS"},
        {"connector": PAYMENT_CONNECTOR, "setting": PAYMENT_CONNECTOR.upper() + "_CREDENTIALS"},
    ],
}


def settings_for(capability_id: str) -> List[str]:
    return [item["setting"] for item in PLACEHOLDER_CONNECTORS.get(str(capability_id), [])]


def refusal(capability_id: str) -> Dict[str, Any]:
    connectors = PLACEHOLDER_CONNECTORS.get(str(capability_id), [])
    return {
        "ok": False,
        "error": "connector unavailable",
        "error_kind": "unavailable",
        "connectors": [item["connector"] for item in connectors],
        "settings": [item["setting"] for item in connectors],
    }


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    if int(status_code) != 503 or not isinstance(body, dict):
        return False
    if body.get("ok") is not False or body.get("error_kind") != "unavailable":
        return False
    return list(body.get("settings") or []) == settings_for(capability_id)
