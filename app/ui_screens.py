"""The console's screen manifest, served at GET /v1/ui.

The console is one page (``app/static/index.html``) with three screens. Each
screen names the capability routes it drives, so the manifest and the page
cannot drift: a screen that claimed a capability the product does not serve
would be a facade, and the manifest says so before an operator clicks.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import authority

#: screen id -> (title, purpose, capability ids the screen calls).
_SCREENS: Dict[str, Dict[str, Any]] = {
    "command_center": {
        "title": "Command center",
        "authority": authority.label(2),
        "purpose": "List, filter and read every record the operator's tenant holds.",
        "capabilities": [
            "contract_and_boq_source_of_record",
            "progress_claims_and_payment_certificates",
            "delay_damages_tracking",
            "qa_itp_records",
            "document_register",
            "claim_review_and_dispute_resolution",
        ],
    },
    "operational_chat": {
        "title": "Operational chat",
        "authority": authority.label(2),
        "purpose": "Attach a document to the register, ask it a question, and resolve a governing term against the source of record.",
        "capabilities": [
            "document_register",
            "contract_and_boq_source_of_record",
        ],
    },
    "resident_engineer": {
        "title": "Resident engineer",
        "authority": authority.label(3),
        "purpose": "The position at a glance: how many records each capability holds and the authority its answers carry.",
        "capabilities": [
            "contract_and_boq_source_of_record",
            "progress_claims_and_payment_certificates",
            "delay_damages_tracking",
            "qa_itp_records",
            "document_register",
            "claim_review_and_dispute_resolution",
        ],
    },
}


def ui_screens() -> List[Dict[str, Any]]:
    """The console's screens, in navigation order."""
    return [
        {
            "id": screen_id,
            "title": spec["title"],
            "purpose": spec["purpose"],
            "capabilities": list(spec["capabilities"]),
            "routes": ["/v1/" + capability_id for capability_id in spec["capabilities"]],
            "authority": spec["authority"],
        }
        for screen_id, spec in _SCREENS.items()
    ]
