"""Platform package bootstrap.

The Factory-supplied ``app.domain_ops`` module ships with an empty capability table
so the product declares its own: this binds the emitted models into that
table once, at import, without touching the Factory-owned module's source.
"""

from __future__ import annotations


def _type_name(annotation) -> str:
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is bool:
        return "bool"
    return "str"


def _bind_domain_ops() -> None:
    try:
        from app import domain_ops
        from app.models import MODELS
    except Exception:
        return
    if getattr(domain_ops, "SPECS", None):
        return
    for capability_id, cls in MODELS.items():
        annotations = getattr(cls, "__annotations__", {}) or {}
        constraints = getattr(cls, "CONSTRAINTS", {}) or {}
        fields = []
        for name in getattr(cls, "FIELDS", []):
            rule = constraints.get(name) or {}
            field = {
                "name": name,
                "type": _type_name(annotations.get(name)),
                "required": bool(rule.get("required")),
            }
            if rule.get("allowed_values"):
                field["allowed_values"] = list(rule["allowed_values"])
            if rule.get("min") is not None:
                field["min"] = rule["min"]
            if rule.get("max") is not None:
                field["max"] = rule["max"]
            fields.append(field)
        domain_ops.SPECS[capability_id] = {
            "entity": getattr(cls, "ENTITY", capability_id),
            "fields": fields,
        }
    if MODELS:
        first = next(iter(MODELS))
        domain_ops.DEFAULT_CAPABILITY = first
        domain_ops.DEFAULT_ENTITY = getattr(MODELS[first], "ENTITY", first)
        domain_ops.SAMPLE = domain_ops.sample_payload(first)


_bind_domain_ops()
