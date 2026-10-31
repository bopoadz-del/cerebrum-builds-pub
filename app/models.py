"""Capability models: declared fields, constraints and the entity a route stores.

The writer gate, the product suites and the Store harness all build their
POST payload from these declarations, so every field a handler or route
requires is declared here (and nothing stricter is enforced downstream).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Type

STATUS_VALUES = ["open", "in_progress", "closed"]
PLANT_VALUES = ["plant-casablanca", "plant-tanger"]
DOCUMENT_TYPES = ["bom", "work_instruction", "quality_procedure", "supplier_price_list"]

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CapabilityModel:
    CAPABILITY_ID = ""
    ENTITY = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    FIELD_TYPES: Dict[str, str] = {}
    FIELD_DEFAULTS: Dict[str, Any] = {}
    MONEY_FIELDS: List[str] = []
    QUANTITY_FIELDS: List[str] = []
    RESERVED_FIELDS = ("action", "id")

    def __init__(self, **data: Any) -> None:
        for name in self.FIELDS:
            setattr(self, name, data.get(name, self.FIELD_DEFAULTS.get(name)))

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CapabilityModel":
        source = dict(data or {})
        return cls(**{k: v for k, v in source.items() if k in cls.FIELDS})

    def to_dict(self) -> Dict[str, Any]:
        out = {name: getattr(self, name, None) for name in self.FIELDS}
        out["id"] = getattr(self, "id", None)
        return out


def _base(capability_id: str, extra_fields: List[str], constraints: Dict[str, Dict[str, Any]],
          types: Dict[str, str], defaults: Dict[str, Any], money: List[str], quantity: List[str]):
    fields = ["reference", "status"] + extra_fields
    all_constraints: Dict[str, Dict[str, Any]] = {
        "reference": {"type": "str"},
        "status": {"type": "str", "allowed_values": list(STATUS_VALUES)},
    }
    all_constraints.update(constraints)
    all_types = {"reference": "str", "status": "str"}
    all_types.update(types)
    all_defaults = {"reference": None, "status": "open"}
    all_defaults.update(defaults)
    attrs = {
        "CAPABILITY_ID": capability_id,
        "ENTITY": capability_id,
        "FIELDS": fields,
        "CONSTRAINTS": all_constraints,
        "FIELD_TYPES": all_types,
        "FIELD_DEFAULTS": all_defaults,
        "MONEY_FIELDS": money,
        "QUANTITY_FIELDS": quantity,
    }
    return type(capability_id.title().replace("_", "") + "Model", (CapabilityModel,), attrs)


DocumentGroundedQa = _base(
    "document_grounded_qa",
    ["question", "plant", "document_type", "top_k", "answer", "authority", "tenant_scope"],
    {
        "question": {"type": "str", "required": True},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
        "document_type": {"type": "str", "allowed_values": list(DOCUMENT_TYPES)},
        "top_k": {"type": "int", "min": 1, "max": 20},
        "answer": {"type": "str"},
        "authority": {"type": "str"},
        "tenant_scope": {"type": "str"},
    },
    {"question": "str", "plant": "str", "document_type": "str", "top_k": "int",
     "answer": "str", "authority": "str", "tenant_scope": "str"},
    {"top_k": 5},
    [], [],
)

SupplierCostAndPartsPricing = _base(
    "supplier_cost_and_parts_pricing",
    ["invoice_reference", "supplier", "part_number", "amount_mad", "quantity",
     "unit_cost_mad", "price_mad", "plant", "invoice_date", "markup_ratio"],
    {
        "invoice_reference": {"type": "str", "required": True},
        "supplier": {"type": "str"},
        "part_number": {"type": "str"},
        "amount_mad": {"type": "money", "min": 0},
        "quantity": {"type": "quantity", "min": 1},
        "unit_cost_mad": {"type": "money", "min": 0},
        "price_mad": {"type": "money", "min": 0},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
        "invoice_date": {"type": "date"},
        "markup_ratio": {"type": "float"},
    },
    {"invoice_reference": "str", "supplier": "str", "part_number": "str",
     "amount_mad": "money", "quantity": "quantity", "unit_cost_mad": "money",
     "price_mad": "money", "plant": "str", "invoice_date": "date",
     "markup_ratio": "float"},
    {"quantity": 1},
    ["amount_mad", "unit_cost_mad", "price_mad"], ["quantity"],
)

CostPriceMovementAlerts = _base(
    "cost_price_movement_alerts",
    ["alert_reference", "part_number", "supplier", "threshold_mad", "movement_pct",
     "previous_price_mad", "current_price_mad", "alert_level", "plant", "notified"],
    {
        "alert_reference": {"type": "str", "required": True},
        "part_number": {"type": "str"},
        "supplier": {"type": "str"},
        "threshold_mad": {"type": "money", "min": 0, "required": True},
        "movement_pct": {"type": "float"},
        "previous_price_mad": {"type": "money", "min": 0, "required": True},
        "current_price_mad": {"type": "money", "min": 0, "required": True},
        "alert_level": {"type": "str", "allowed_values": ["info", "warning", "critical"]},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
        "notified": {"type": "bool"},
    },
    {"alert_reference": "str", "part_number": "str", "supplier": "str",
     "threshold_mad": "money", "movement_pct": "float",
     "previous_price_mad": "money", "current_price_mad": "money",
     "alert_level": "str", "plant": "str", "notified": "bool"},
    {"alert_level": "warning", "notified": False},
    ["threshold_mad", "previous_price_mad", "current_price_mad"], [],
)

DocumentRevisionNudges = _base(
    "document_revision_nudges",
    ["document_name", "document_type", "revision_from", "revision_to",
     "manager_email", "plant", "notified"],
    {
        "document_name": {"type": "str", "required": True},
        "document_type": {"type": "str", "allowed_values": list(DOCUMENT_TYPES)},
        "revision_from": {"type": "str"},
        "revision_to": {"type": "str"},
        "manager_email": {"type": "str", "format": "email"},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
        "notified": {"type": "bool"},
    },
    {"document_name": "str", "document_type": "str", "revision_from": "str",
     "revision_to": "str", "manager_email": "str", "plant": "str", "notified": "bool"},
    {"document_type": "work_instruction", "notified": False},
    [], [],
)

DocumentIngestionFromM365AndUpload = _base(
    "document_ingestion_from_m365_and_upload",
    ["document_name", "source", "document_type", "content_text", "drive_item_id", "file_path", "plant"],
    {
        "document_name": {"type": "str", "required": True},
        "source": {"type": "str", "allowed_values": ["onedrive", "outlook", "upload"]},
        "document_type": {"type": "str", "allowed_values": list(DOCUMENT_TYPES)},
        "content_text": {"type": "str"},
        "drive_item_id": {"type": "str"},
        "file_path": {"type": "str"},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
    },
    {"document_name": "str", "source": "str", "document_type": "str",
     "content_text": "str", "drive_item_id": "str", "file_path": "str", "plant": "str"},
    {"source": "upload", "document_type": "bom"},
    [], [],
)

ManagerDashboard = _base(
    "manager_dashboard",
    ["plant", "period_start", "period_end", "include_alerts", "layout"],
    {
        "plant": {"type": "str", "allowed_values": ["plant-casablanca", "plant-tanger", "all"]},
        "period_start": {"type": "date"},
        "period_end": {"type": "date"},
        "include_alerts": {"type": "bool"},
        "layout": {"type": "str"},
    },
    {"plant": "str", "period_start": "date", "period_end": "date",
     "include_alerts": "bool", "layout": "str"},
    {"plant": "all", "include_alerts": True},
    [], [],
)

ManagerOnlyAccess = _base(
    "manager_only_access",
    ["manager_name", "manager_email", "role", "plant"],
    {
        "manager_name": {"type": "str"},
        "manager_email": {"type": "str", "format": "email", "required": True},
        "role": {"type": "str", "allowed_values": ["manager"]},
        "plant": {"type": "str", "allowed_values": list(PLANT_VALUES)},
    },
    {"manager_name": "str", "manager_email": "str", "role": "str", "plant": "str"},
    {"role": "manager"},
    [], [],
)

SapOdataConnector = _base(
    "sap_odata_connector",
    ["company_code", "operation", "base_url"],
    {
        "company_code": {"type": "str"},
        "operation": {"type": "str", "allowed_values": ["status", "list_gl_accounts", "list_po_headers"]},
        "base_url": {"type": "str"},
    },
    {"company_code": "str", "operation": "str", "base_url": "str"},
    {"operation": "status"},
    [], [],
)

MODELS: Dict[str, Type[CapabilityModel]] = {
    cls.CAPABILITY_ID: cls
    for cls in (
        DocumentGroundedQa,
        SupplierCostAndPartsPricing,
        CostPriceMovementAlerts,
        DocumentRevisionNudges,
        DocumentIngestionFromM365AndUpload,
        ManagerDashboard,
        ManagerOnlyAccess,
        SapOdataConnector,
    )
}

CAPABILITY_IDS = list(MODELS)


def _check_type(name: str, kind: str, value: Any) -> Optional[str]:
    if kind in ("int", "quantity"):
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{name} must be an integer"
    elif kind in ("float", "money"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{name} must be a number"
    elif kind == "bool":
        if not isinstance(value, bool):
            return f"{name} must be a boolean"
    else:
        if not isinstance(value, str):
            return f"{name} must be a string"
    return None


def validate_payload(capability_id: str, payload: Optional[Dict[str, Any]]):
    """Return (normalized, rejection). A rejection is a typed field record."""
    cls = MODELS.get(capability_id)
    if cls is None:
        return None, {"field": capability_id, "reason": "unknown_capability"}
    if not isinstance(payload, dict):
        return None, {"field": "body", "reason": "not_an_object"}
    for reserved in cls.RESERVED_FIELDS:
        if reserved in payload:
            return None, {"field": reserved, "reason": "reserved_keyword"}
    normalized: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = cls.CONSTRAINTS.get(name) or {}
        kind = cls.FIELD_TYPES.get(name, "str")
        present = name in payload and payload[name] not in (None, "")
        if not present:
            if rules.get("required"):
                return None, {"field": name, "reason": "missing_required"}
            continue
        value = payload[name]
        type_error = _check_type(name, kind, value)
        if type_error:
            return None, {"field": name, "reason": "wrong_type", "detail": type_error}
        allowed = rules.get("allowed_values")
        if allowed and value not in allowed:
            return None, {"field": name, "reason": "not_allowed", "allowed_values": list(allowed)}
        if "min" in rules and isinstance(value, (int, float)) and value < rules["min"]:
            return None, {"field": name, "reason": "below_minimum", "min": rules["min"]}
        if "max" in rules and isinstance(value, (int, float)) and value > rules["max"]:
            return None, {"field": name, "reason": "above_maximum", "max": rules["max"]}
        if rules.get("format") == "email" and not _EMAIL_RE.match(str(value)):
            return None, {"field": name, "reason": "invalid_format", "format": "email"}
        if rules.get("format") == "date" or kind == "date":
            if not _DATE_RE.match(str(value)):
                return None, {"field": name, "reason": "invalid_format", "format": "date"}
        normalized[name] = value
    return normalized, None
