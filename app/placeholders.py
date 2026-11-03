"""Declared placeholder connectors.

Five capabilities call an integration the blueprint declares but the
platform does not build. Their POST answers HTTP 503 with error_kind
"unavailable" naming the setting the operator must supply, before the
handler runs and before anything is stored. tests/test_placeholder_contract.py
is the authority on this answer.

The connectors not declared here are implemented: document_register and
claim_evidence_and_approvals persist real records.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

PLACEHOLDER_CONNECTORS: Dict[str, Dict[str, Any]] = {
    "progress_claims": {
        "connectors": ["project_accounting_ledger"],
        "settings": ["PROJECT_ACCOUNTING_LEDGER_CREDENTIALS"],
    },
    "delay_damages_tracking": {
        "connectors": ["primavera_p6_schedule"],
        "settings": ["PRIMAVERA_P6_SCHEDULE_CREDENTIALS"],
    },
    "qa_itp_records": {
        "connectors": ["project_edms"],
        "settings": ["PROJECT_EDMS_CREDENTIALS"],
    },
    "performance_security_tracking": {
        "connectors": ["bank_guarantee_and_surety_provider"],
        "settings": ["BANK_GUARANTEE_AND_SURETY_PROVIDER_CREDENTIALS"],
    },
    "defects_notification_period": {
        "connectors": ["defects_and_maintenance_system"],
        "settings": ["DEFECTS_AND_MAINTENANCE_SYSTEM_CREDENTIALS"],
    },
}


def refusal_body(capability_id: str) -> Dict[str, Any]:
    declared = PLACEHOLDER_CONNECTORS[capability_id]
    return {
        "ok": False,
        "error_kind": "unavailable",
        "capability_id": capability_id,
        "connectors": list(declared["connectors"]),
        "settings": list(declared["settings"]),
        "error": "connector unavailable: set " + ", ".join(declared["settings"]),
    }


def is_declared_refusal(capability_id: str, status_code: int, body: Any) -> bool:
    if int(status_code) != 503 or not isinstance(body, Mapping):
        return False
    if body.get("error_kind") != "unavailable" or body.get("ok") is not False:
        return False
    declared = PLACEHOLDER_CONNECTORS.get(str(capability_id))
    return bool(declared) and list(body.get("settings") or []) == list(declared["settings"])
