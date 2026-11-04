"""Bridge from the capability models to the kernel action contract."""

from __future__ import annotations

from typing import Any, Dict, List

from app import domain_ops
from app.models import CAPABILITY_ORDER, MODELS

_JSON_TYPES = {"str": "str", "int": "int", "float": "float", "bool": "bool", "date": "date"}


def _field_spec(cls) -> List[Dict[str, Any]]:
    out = []
    for name in cls.FIELDS:
        rules = dict(cls.CONSTRAINTS.get(name) or {})
        item: Dict[str, Any] = {
            "name": name,
            "type": _JSON_TYPES.get(cls.TYPES.get(name, "str"), "string"),
        }
        if rules.get("required"):
            item["required"] = True
        if rules.get("allowed_values"):
            item["allowed_values"] = list(rules["allowed_values"])
        if "min" in rules:
            item["min"] = rules["min"]
        if "max" in rules:
            item["max"] = rules["max"]
        out.append(item)
    return out


def sample_payload(capability_id: str) -> Dict[str, Any]:
    cls = MODELS.get(str(capability_id))
    if cls is None:
        raise KeyError("unknown capability_id: %s" % capability_id)
    payload: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = cls.CONSTRAINTS.get(name) or {}
        allowed = rules.get("allowed_values") or []
        kind = cls.TYPES.get(name, "str")
        if allowed:
            payload[name] = allowed[0]
        elif kind == "int":
            payload[name] = int(rules.get("min") or 1)
        elif kind == "float":
            payload[name] = float(rules.get("min") or 1.5)
        elif kind == "bool":
            payload[name] = False
        elif kind == "date":
            payload[name] = "2026-09-03"
        else:
            payload[name] = "sample"
    return payload


def register() -> None:
    """Populate the kernel's capability registry from the models."""
    if domain_ops.SPECS:
        return
    for capability_id in CAPABILITY_ORDER:
        cls = MODELS[capability_id]
        domain_ops.SPECS[capability_id] = {
            "entity": cls.ENTITY,
            "fields": _field_spec(cls),
        }
    domain_ops.DEFAULT_CAPABILITY = CAPABILITY_ORDER[0]
    domain_ops.SAMPLE = sample_payload(CAPABILITY_ORDER[0])


def spec_for(capability_id: str):
    register()
    return domain_ops.spec_for_op("create", str(capability_id))


register()
