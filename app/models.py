"""Capability models for the Delivery Service Platform.

Every model carries its own FIELDS, CONSTRAINTS and ENTITY.  The entity name
is the capability id: that is the table the migration creates, the table the
route saves to, and the name the store reads back.  A model never invents a
field at request time -- a payload built from FIELDS is a payload the route
accepts.
"""

from __future__ import annotations

from typing import Any, Dict, List


class RecordModel:
    ENTITY = ""
    FIELDS: List[str] = []
    CONSTRAINTS: Dict[str, Dict[str, Any]] = {}
    MONEY_FIELDS: List[str] = []
    QUANTITY_FIELDS: List[str] = []

    def __init__(self, **data: Any) -> None:
        for name in self.FIELDS:
            setattr(self, name, data.get(name))
        self.id = data.get("id")
        self.tenant_id = data.get("tenant_id")
        self.created_at = data.get("created_at")

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "RecordModel":
        return cls(**(data or {}))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {name: getattr(self, name, None) for name in self.FIELDS}
        out["id"] = self.id
        if self.tenant_id is not None:
            out["tenant_id"] = self.tenant_id
        if self.created_at is not None:
            out["created_at"] = self.created_at
        return out

    @classmethod
    def field_specs(cls) -> List[Dict[str, Any]]:
        specs = []
        for name in cls.FIELDS:
            rules = dict(cls.CONSTRAINTS.get(name) or {})
            spec = {"name": name, "type": rules.get("type", "str")}
            spec.update(rules)
            spec["name"] = name
            specs.append(spec)
        return specs


_ENVELOPE = {
    "reference": {"required": True, "type": "str"},
    "status": {
        "required": True,
        "type": "str",
        "allowed_values": ["open", "in_progress", "closed"],
    },
    "notes": {"type": "str"},
}


class CustomerBookingFlow(RecordModel):
    ENTITY = "customer_booking_flow"
    FIELDS = [
        "reference", "status", "notes", "customer_name", "customer_email",
        "contractor_reference", "suburb", "booking_date", "start_time",
        "end_time", "service_type", "quoted_amount", "cost_amount",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "customer_name": {"type": "str"},
        "customer_email": {"type": "str", "format": "email"},
        "contractor_reference": {"required": True, "type": "str"},
        "suburb": {"required": True, "type": "str"},
        "booking_date": {"required": True, "type": "str", "format": "date"},
        "start_time": {"required": True, "type": "str", "format": "time"},
        "end_time": {"required": True, "type": "str", "format": "time"},
        "service_type": {"type": "str"},
        "quoted_amount": {"type": "money", "min": 0},
        "cost_amount": {"type": "money", "min": 0},
    }
    MONEY_FIELDS = ["quoted_amount", "cost_amount"]


class ContractorOnboardingAndServiceAreas(RecordModel):
    ENTITY = "contractor_onboarding_and_service_areas"
    FIELDS = [
        "reference", "status", "notes", "contractor_name", "contact_email",
        "phone", "service_suburbs", "pending_suburbs", "retired_suburbs",
        "catalogue_state", "vehicle_type", "capacity", "active",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "contractor_name": {"required": True, "type": "str"},
        "contact_email": {"type": "str", "format": "email"},
        "phone": {"type": "str"},
        "service_suburbs": {"required": True, "type": "str"},
        "pending_suburbs": {"type": "str"},
        "retired_suburbs": {"type": "str"},
        "catalogue_state": {"type": "str"},
        "vehicle_type": {"type": "str"},
        "capacity": {"type": "int", "min": 1},
        "active": {"type": "bool"},
    }


class ContractorAvailabilitySchedule(RecordModel):
    ENTITY = "contractor_availability_schedule"
    FIELDS = [
        "reference", "status", "notes", "contractor_reference", "weekday",
        "start_time", "end_time", "capacity", "active",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "contractor_reference": {"required": True, "type": "str"},
        "weekday": {
            "required": True,
            "type": "str",
            "allowed_values": [
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday",
            ],
        },
        "start_time": {"required": True, "type": "str", "format": "time"},
        "end_time": {"required": True, "type": "str", "format": "time"},
        "capacity": {"type": "int", "min": 1},
        "active": {"type": "bool"},
    }
    QUANTITY_FIELDS = ["capacity"]


class LocationBasedMatching(RecordModel):
    ENTITY = "location_based_matching"
    FIELDS = [
        "reference", "status", "notes", "booking_reference", "suburb",
        "contractor_reference", "booking_date", "start_time", "distance_km",
        "required_skills",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "booking_reference": {"required": True, "type": "str"},
        "suburb": {"required": True, "type": "str"},
        "contractor_reference": {"required": True, "type": "str"},
        "booking_date": {"required": True, "type": "str", "format": "date"},
        "start_time": {"required": True, "type": "str", "format": "time"},
        "distance_km": {"type": "float", "min": 0},
        "required_skills": {"type": "str"},
    }


class BookingStatusLifecycle(RecordModel):
    ENTITY = "booking_status_lifecycle"
    _STATES = ["requested", "accepted", "in_progress", "completed", "cancelled"]
    FIELDS = [
        "reference", "status", "notes", "booking_reference", "current_state",
        "target_state", "actor", "transition_id",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "booking_reference": {"required": True, "type": "str"},
        "current_state": {"required": True, "type": "str", "allowed_values": list(_STATES)},
        "target_state": {"required": True, "type": "str", "allowed_values": list(_STATES)},
        "actor": {
            "required": True,
            "type": "str",
            "allowed_values": ["customer", "contractor", "operator", "system"],
        },
        "transition_id": {"type": "str"},
    }


class BookingNotifications(RecordModel):
    ENTITY = "booking_notifications"
    FIELDS = [
        "reference", "status", "notes", "booking_reference", "recipient_email",
        "recipient_phone", "channel", "message", "event_type",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "booking_reference": {"required": True, "type": "str"},
        "recipient_email": {"type": "str", "format": "email"},
        "recipient_phone": {"type": "str"},
        "channel": {"type": "str", "allowed_values": ["email", "sms", "webhook"]},
        "message": {"type": "str"},
        "event_type": {"type": "str"},
    }


class InvoicingAndPayouts(RecordModel):
    ENTITY = "invoicing_and_payouts"
    FIELDS = [
        "reference", "status", "notes", "booking_reference", "amount",
        "units", "payee_reference", "invoice_reference", "payout_stage",
        "released_amount",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "booking_reference": {"required": True, "type": "str"},
        "amount": {"required": True, "type": "money", "min": 0},
        "units": {"type": "quantity", "min": 0},
        "payee_reference": {"type": "str"},
        "invoice_reference": {"type": "str"},
        "payout_stage": {
            "type": "str",
            "allowed_values": ["hold", "fee_quote", "release", "partial_release", "refund"],
        },
        "released_amount": {"type": "money", "min": 0},
    }
    MONEY_FIELDS = ["amount", "released_amount"]
    QUANTITY_FIELDS = ["units"]


class OpsBackOffice(RecordModel):
    ENTITY = "ops_back_office"
    FIELDS = [
        "reference", "status", "notes", "dispute_reference", "booking_reference",
        "claimant", "claim_type", "suburb", "region", "resolution_notes",
        "dispute_action", "resolution", "maintain_suburbs", "suburb_active",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "dispute_reference": {"type": "str"},
        "booking_reference": {"type": "str"},
        "claimant": {"type": "str"},
        "claim_type": {"type": "str"},
        "suburb": {"type": "str"},
        "region": {"type": "str"},
        "resolution_notes": {"type": "str"},
        "dispute_action": {
            "type": "str",
            "allowed_values": ["open", "escalate", "resolve", "status"],
        },
        "resolution": {
            "type": "str",
            "allowed_values": ["released", "refunded", "dismissed"],
        },
        "maintain_suburbs": {"type": "bool"},
        "suburb_active": {"type": "bool"},
    }


class Audit(RecordModel):
    ENTITY = "audit"
    FIELDS = [
        "reference", "status", "notes", "event", "resource_type",
        "resource_id", "details", "actor", "sequence", "previous_digest",
        "chain_digest",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "event": {"required": True, "type": "str"},
        "resource_type": {"type": "str"},
        "resource_id": {"type": "str"},
        "details": {"type": "str"},
        "actor": {"type": "str"},
        "sequence": {"type": "int", "min": 0},
        "previous_digest": {"type": "str"},
        "chain_digest": {"type": "str"},
    }


class Config(RecordModel):
    ENTITY = "config"
    FIELDS = [
        "reference", "status", "notes", "config_block", "key", "value",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "config_block": {"required": True, "type": "str"},
        "key": {"type": "str"},
        "value": {"type": "str"},
    }


class Email(RecordModel):
    ENTITY = "email"
    FIELDS = [
        "reference", "status", "notes", "recipient_email", "subject", "body",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "recipient_email": {"required": True, "type": "str", "format": "email"},
        "subject": {"type": "str"},
        "body": {"type": "str"},
    }


class Billing(RecordModel):
    ENTITY = "billing"
    FIELDS = [
        "reference", "status", "notes", "api_key", "block_used", "tokens",
        "plan",
    ]
    CONSTRAINTS = {
        **_ENVELOPE,
        "api_key": {"type": "str"},
        "block_used": {"type": "str"},
        "tokens": {"type": "int", "min": 0},
        "plan": {
            "type": "str",
            "allowed_values": ["free", "pro", "enterprise"],
        },
    }


MODELS: Dict[str, type] = {
    "customer_booking_flow": CustomerBookingFlow,
    "contractor_onboarding_and_service_areas": ContractorOnboardingAndServiceAreas,
    "contractor_availability_schedule": ContractorAvailabilitySchedule,
    "location_based_matching": LocationBasedMatching,
    "booking_status_lifecycle": BookingStatusLifecycle,
    "booking_notifications": BookingNotifications,
    "invoicing_and_payouts": InvoicingAndPayouts,
    "ops_back_office": OpsBackOffice,
    "audit": Audit,
    "config": Config,
    "email": Email,
    "billing": Billing,
}

CAPABILITIES = list(MODELS)

#: Supporting entity the ops back office maintains.  It is not a capability
#: (no handler, no POST /v1/service_suburb): it is the tenant's managed
#: suburb catalogue that contractor onboarding and matching read.
SERVICE_SUBURB_ENTITY = "service_suburb"
SERVICE_SUBURB_COLUMNS = [
    "reference", "status", "notes", "suburb", "region", "active",
]
