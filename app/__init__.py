"""Harbourline Civil Works contracts administration -- product package.

The package import is deliberately cheap: importing ``app`` must work with an
EMPTY environment (CI boots ``import app.main`` before any credential exists),
so nothing here reads a setting, opens a database, or loads a block. The only
work done here is binding the kernel's domain-operation registry to this
product's capabilities, which is pure declaration built from ``app.models``.
"""

from __future__ import annotations

__all__ = ["PRODUCT_ID", "PRODUCT_NAME", "SCREENS", "__version__", "ui_screens"]

__version__ = "1.0.0"


def _product_id() -> str:
    """The manufacturing identifier, read from the source-of-record data."""
    try:
        from app import sources

        return sources.PRODUCT_ID
    except Exception:  # pragma: no cover - a broken data file fails at the gate
        return "platform"


PRODUCT_ID = _product_id()
PRODUCT_NAME = "Harbourline Civil Works contracts administration"


#: The one console's screens. Each screen is served at the hash route named
#: here, drives the capability ids listed with it, and shows the authority
#: label every route answer carries. app/static/index.html renders them; the
#: console reads this manifest through GET /v1/ui.
SCREENS = {
    "command_center": {
        "route": "/#/command_center",
        "capabilities": [
            "contract_and_boq_source_of_record",
            "progress_claims_and_payment_certificates",
        ],
        "purpose": "discover capabilities, create a record and list the caller's records",
    },
    "operational_chat": {
        "route": "/#/operational_chat",
        "capabilities": [
            "contract_and_boq_source_of_record",
            "document_register",
        ],
        "purpose": "attach a document, ask a question and read the cited answer",
    },
    "resident_engineer": {
        "route": "/#/resident_engineer",
        "capabilities": [
            "delay_damages_tracking",
            "qa_itp_records",
            "document_register",
        ],
        "purpose": "the position across every capability, with record counts and authority",
    },
}


def ui_screens() -> dict:
    """The console manifest the served UI and the platform both read."""
    return {name: dict(spec) for name, spec in SCREENS.items()}


def _bind_domain_ops() -> None:
    try:
        from app import kernel_bridge
    except Exception:  # pragma: no cover - a broken tree fails at the gate
        return
    kernel_bridge.bind_domain_ops()


_bind_domain_ops()
