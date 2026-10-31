"""SAP ERP OData adapter surface for costing and invoicing data."""

from __future__ import annotations

from typing import Any, Dict

from app.actions._common import block_failure, envelope
from app.dispatch import execute

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "sap_odata_connector"
ENTITY = "sap_odata_connector"
BLOCK_IDS = ["sap_odata_connector"]
BLOCK_DEFAULT_ACTIONS = {"sap_odata_connector": "status"}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "env", "scope": "process"},
    {"kind": "config", "scope": "runtime"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    operation = str(record.get("operation") or "status")
    answer = execute(
        "sap_odata_connector",
        {"action": operation},
        action=BLOCK_DEFAULT_ACTIONS.get("sap_odata_connector"),
    )
    refused = block_failure("sap_odata_connector", answer)
    if refused:
        return refused
    return envelope(
        {
            "operation": operation,
            "company_code": str(record.get("company_code") or ""),
            "configured": bool(answer.get("configured")),
            "missing": answer.get("missing") or [],
            "implemented": bool(answer.get("implemented")),
            "read_only_surface": answer.get("read_only_surface") or [],
            "rows": answer.get("rows") or [],
        },
        record,
    )
