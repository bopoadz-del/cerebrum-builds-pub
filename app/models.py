"""Declared schema of the coffee-compost factory platform.

Written by the factory WRITER role (codewhale exec).

Envelope status vocabulary is schema-enforced (open | in_progress | closed).
Money fields carry ``format: money`` and are listed in ``MONEY_FIELDS``;
counts and weights carry ``format: quantity`` and are listed in
``QUANTITY_FIELDS``. Country, currency and every rate come from
app.money_settings at the point of use -- no currency code and no tax rate is
a literal here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

ENVELOPE_STATUS = ["open", "in_progress", "closed"]
SOURCE_TYPES = ["cafe", "restaurant", "hotel", "roastery", "office", "other"]
PICKUP_PRIORITIES = ["normal", "high", "low"]
INPUT_MATERIALS = ["coffee_grounds", "coffee_husk", "mixed_organic", "bulking_agent", "other"]
BATCH_STAGES = [
    "mixing", "active_composting", "curing", "screening",
    "quality_check", "packaged", "rejected",
]
QUALITY_RESULTS = ["pending", "pass", "fail"]
CUSTOMER_TYPES = ["retail", "wholesale", "municipal", "agriculture", "other"]
PRICE_LISTS = ["retail", "wholesale", "contract"]
SUPPLY_TYPES = ["goods", "services", "mixed"]
PAYMENT_STATES = ["unpaid", "partial", "paid"]
STAFF_ROLES = [
    "collection_logistics", "production_floor", "sales", "finance",
    "manager", "admin",
]
ACCESS_STATES = ["invited", "active", "suspended", "revoked"]


class _Model:
    """The two conversions every capability model shares."""

    ENTITY = ""
    FIELDS: list = []
    CONSTRAINTS: Dict[str, Any] = {}
    MONEY_FIELDS: list = []
    QUANTITY_FIELDS: list = []
    _FIELD_PY: Dict[str, str] = {}
    _FIELD_JSON: Dict[str, str] = {}

    def __init__(self, **values: Any) -> None:
        for name in ("id",) + tuple(self.FIELDS):
            if name in values:
                setattr(self, self._FIELD_PY.get(name, name), values[name])

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name in self.FIELDS:
            out[name] = getattr(self, self._FIELD_PY.get(name, name), None)
        out["id"] = getattr(self, "id", None)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        known: Dict[str, Any] = {}
        payload = dict(data or {})
        for name in cls.FIELDS:
            if name in payload:
                known[cls._FIELD_PY.get(name, name)] = payload[name]
        return cls(id=payload.get("id"), **known)


class CollectionPlanningTracking(_Model):
    """One coffee-waste collection: source, planned pickup and what arrived."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    source_name: str = ""
    source_type: str = "cafe"
    source_address: str = ""
    pickup_lat: float = 0.0
    pickup_lng: float = 0.0
    pickup_date: str = ""
    planned_kg: float = 0.0
    collected_kg: float = 0.0
    moisture_pct: float = 0.0
    crew: str = ""
    vehicle_id: str = ""
    priority: str = "normal"
    delivered_on: str = ""
    notes: str = ""

    ENTITY = "collection_planning_tracking"
    FIELDS = [
        "reference", "status", "source_name", "source_type", "source_address",
        "pickup_lat", "pickup_lng", "pickup_date", "planned_kg",
        "collected_kg", "moisture_pct", "crew", "vehicle_id", "priority",
        "delivered_on", "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "source_name": {"required": True},
        "source_type": {"allowed_values": SOURCE_TYPES},
        "pickup_lat": {"min": -90, "max": 90},
        "pickup_lng": {"min": -180, "max": 180},
        "pickup_date": {"format": "date"},
        "planned_kg": {"format": "quantity", "min": 0},
        "collected_kg": {"format": "quantity", "min": 0},
        "moisture_pct": {"min": 0, "max": 100},
        "priority": {"allowed_values": PICKUP_PRIORITIES},
        "delivered_on": {"format": "datetime", "not_before": "pickup_date"},
    }
    QUANTITY_FIELDS = ["planned_kg", "collected_kg"]


class BatchProductionTracking(_Model):
    """One compost batch through production, curing and quality check."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    batch_code: str = ""
    input_material: str = "coffee_grounds"
    input_kg: float = 0.0
    stage: str = "mixing"
    started_on: str = ""
    curing_days: int = 0
    temperature_c: float = 0.0
    moisture_pct: float = 0.0
    ph: float = 7.0
    c_n_ratio: float = 25.0
    quality_result: str = "pending"
    output_kg: float = 0.0
    notes: str = ""

    ENTITY = "batch_production_tracking"
    FIELDS = [
        "reference", "status", "batch_code", "input_material", "input_kg",
        "stage", "started_on", "curing_days", "temperature_c", "moisture_pct",
        "ph", "c_n_ratio", "quality_result", "output_kg", "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "batch_code": {"required": True},
        "input_material": {"allowed_values": INPUT_MATERIALS},
        "input_kg": {"format": "quantity", "min": 0},
        "stage": {"allowed_values": BATCH_STAGES, "required": True},
        "started_on": {"format": "date"},
        "curing_days": {"min": 0},
        "temperature_c": {"min": 0, "max": 90},
        "moisture_pct": {"min": 0, "max": 100},
        "ph": {"min": 3, "max": 10},
        "c_n_ratio": {"min": 5, "max": 60},
        "quality_result": {"allowed_values": QUALITY_RESULTS},
        "output_kg": {"format": "quantity", "min": 0},
    }
    QUANTITY_FIELDS = ["input_kg", "output_kg"]


class CatalogPricingOrders(_Model):
    """One customer order line against the product catalog and price list."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    order_number: str = ""
    customer_name: str = ""
    customer_type: str = "retail"
    product_sku: str = ""
    product_name: str = ""
    price_list: str = "retail"
    quantity: float = 0.0
    unit_price: float = 0.0
    discount_pct: float = 0.0
    order_date: str = ""
    notes: str = ""

    ENTITY = "catalog_pricing_orders"
    FIELDS = [
        "reference", "status", "order_number", "customer_name", "customer_type",
        "product_sku", "product_name", "price_list", "quantity", "unit_price",
        "discount_pct", "order_date", "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "order_number": {"required": True},
        "customer_name": {"required": True},
        "customer_type": {"allowed_values": CUSTOMER_TYPES},
        "product_sku": {"required": True},
        "price_list": {"allowed_values": PRICE_LISTS},
        "quantity": {"format": "quantity", "min": 0},
        "unit_price": {"format": "money", "min": 0},
        "discount_pct": {"min": 0, "max": 100},
        "order_date": {"format": "date"},
    }
    MONEY_FIELDS = ["unit_price"]
    QUANTITY_FIELDS = ["quantity"]


class InvoicingTunisianVat(_Model):
    """One invoice in Tunisian dinar with its net, VAT and gross totals."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    invoice_number: str = ""
    customer_name: str = ""
    customer_tax_id: str = ""
    supply_type: str = "goods"
    quantity: float = 0.0
    unit_price_ht: float = 0.0
    vat_exempt: bool = False
    vat_rate: float = 0.0
    invoice_date: str = ""
    due_date: str = ""
    payment_state: str = "unpaid"
    notes: str = ""

    ENTITY = "invoicing_tunisian_vat"
    FIELDS = [
        "reference", "status", "invoice_number", "customer_name",
        "customer_tax_id", "supply_type", "quantity", "unit_price_ht",
        "vat_exempt", "vat_rate", "invoice_date", "due_date", "payment_state",
        "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "invoice_number": {"required": True},
        "customer_name": {"required": True},
        "supply_type": {"allowed_values": SUPPLY_TYPES},
        "quantity": {"format": "quantity", "min": 0},
        "unit_price_ht": {"format": "money", "min": 0},
        "vat_rate": {"min": 0, "max": 1},
        "invoice_date": {"format": "date"},
        "due_date": {"format": "date", "not_before": "invoice_date"},
        "payment_state": {"allowed_values": PAYMENT_STATES},
    }
    MONEY_FIELDS = ["unit_price_ht"]
    QUANTITY_FIELDS = ["quantity"]


class InternalStaffAccess(_Model):
    """One member of staff, their role, access state and approver."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    principal_id: str = ""
    principal_name: str = ""
    principal_email: str = ""
    role: str = "collection_logistics"
    access_state: str = "invited"
    approved_by: str = ""
    team_id: str = ""
    last_seen_at: str = ""
    notes: str = ""

    ENTITY = "internal_staff_access"
    FIELDS = [
        "reference", "status", "principal_id", "principal_name",
        "principal_email", "role", "access_state", "approved_by", "team_id",
        "last_seen_at", "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "principal_id": {"required": True},
        "principal_name": {"required": True},
        "principal_email": {"format": "email"},
        "role": {"allowed_values": STAFF_ROLES, "required": True},
        "access_state": {"allowed_values": ACCESS_STATES},
        "approved_by": {
            "approval": True,
            "approval_when": {"field": "access_state", "values": ["revoked"]},
        },
        "last_seen_at": {"format": "datetime"},
    }


class OperationalDashboard(_Model):
    """One operational reading across collections, batches, orders, invoices."""

    id: Optional[int] = None
    reference: str = ""
    status: str = "open"
    report_date: str = ""
    collections_open: int = 0
    batches_in_curing: int = 0
    orders_open: int = 0
    invoices_unpaid: int = 0
    revenue_total: float = 0.0
    quality_failures: int = 0
    notes: str = ""

    ENTITY = "operational_dashboard"
    FIELDS = [
        "reference", "status", "report_date", "collections_open",
        "batches_in_curing", "orders_open", "invoices_unpaid", "revenue_total",
        "quality_failures", "notes",
    ]
    CONSTRAINTS = {
        "reference": {"required": True},
        "status": {"allowed_values": ENVELOPE_STATUS, "required": True},
        "report_date": {"format": "date"},
        "collections_open": {"min": 0},
        "batches_in_curing": {"min": 0},
        "orders_open": {"min": 0},
        "invoices_unpaid": {"min": 0},
        "revenue_total": {"format": "money", "min": 0},
        "quality_failures": {"min": 0},
    }
    MONEY_FIELDS = ["revenue_total"]

    #: Fields the route derives from the platform's own records for the
    #: caller's tenant, never from what the caller typed. A dashboard is a
    #: reading of the factory, so its counts are measured; a caller who posts
    #: a number is overridden by the store. Each rule names the entity and the
    #: declared-column values that make a row part of that queue.
    AGGREGATES = {
        "collections_open": {
            "entity": "collection_planning_tracking",
            "any_of": {"status": ["open", "in_progress"]},
        },
        "batches_in_curing": {
            "entity": "batch_production_tracking",
            "filters": {"stage": "curing"},
            "any_of": {"status": ["open", "in_progress"]},
        },
        "orders_open": {
            "entity": "catalog_pricing_orders",
            "any_of": {"status": ["open", "in_progress"]},
        },
        "invoices_unpaid": {
            "entity": "invoicing_tunisian_vat",
            "any_of": {"payment_state": ["unpaid", "partial"]},
        },
        "quality_failures": {
            "entity": "batch_production_tracking",
            "filters": {"quality_result": "fail"},
        },
        "revenue_total": {
            "entity": "invoicing_tunisian_vat",
            "sum": {"column": "unit_price_ht", "multiply_by": "quantity"},
            "any_of": {"payment_state": ["paid"]},
        },
    }


#: The capability roster: entity name == capability id == handler module stem.
MODELS: Dict[str, Any] = {
    "collection_planning_tracking": CollectionPlanningTracking,
    "batch_production_tracking": BatchProductionTracking,
    "catalog_pricing_orders": CatalogPricingOrders,
    "invoicing_tunisian_vat": InvoicingTunisianVat,
    "internal_staff_access": InternalStaffAccess,
    "operational_dashboard": OperationalDashboard,
}
