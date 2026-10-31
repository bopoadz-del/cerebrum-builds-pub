"""Declared placeholder connectors.

These capabilities call an integration the blueprint declares as a
placeholder. Until the operator supplies the named setting, the POST route
answers HTTP 503 with ``error_kind`` ``unavailable`` before the handler runs
and stores nothing. app.placeholders is the single source of that answer.
"""

from __future__ import annotations

from typing import Dict, List

PLACEHOLDER_CONNECTORS: Dict[str, List[str]] = {
    "supplier_cost_and_parts_pricing": ["SAP_ERP_CREDENTIALS"],
    "cost_price_movement_alerts": ["OUTLOOK_CREDENTIALS"],
    "document_ingestion_from_m365_and_upload": ["OUTLOOK_CREDENTIALS"],
}

CONNECTOR_DETAIL = {
    "SAP_ERP_CREDENTIALS": "SAP ERP OData base URL, user and password",
    "OUTLOOK_CREDENTIALS": "Microsoft 365 Outlook sender credentials",
}


def missing_settings(capability_id: str) -> List[str]:
    """The connectors this capability declares that have no adapter.

    A declared placeholder has no donor implementation in this image, so
    setting its environment variable does not make the integration real.
    The refusal is unconditional: the capability answers 503 and stores
    nothing rather than inventing ERP rows or claiming an email was sent.
    """
    return list(PLACEHOLDER_CONNECTORS.get(capability_id, []))


def refusal(capability_id: str, missing: List[str]) -> dict:
    return {
        "ok": False,
        "error_kind": "unavailable",
        "error": "declared placeholder connector(s) are not configured",
        "capability_id": capability_id,
        "settings": list(missing),
        "connectors": [CONNECTOR_DETAIL.get(name, name) for name in missing],
    }


def is_declared_refusal(capability_id: str, status_code: int, body) -> bool:
    if int(status_code) != 503 or not isinstance(body, dict):
        return False
    return body.get("error_kind") == "unavailable" and capability_id in PLACEHOLDER_CONNECTORS
