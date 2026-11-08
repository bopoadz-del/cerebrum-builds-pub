"""The capability spec table the kernel/domain-ops path reads.

Built from app.models so the declaration a route validates and the
declaration the kernel validates can never drift apart.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import models


def _field(name: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(rules.get("type") or "str")
    entry: Dict[str, Any] = {"name": name, "type": kind}
    if rules.get("required"):
        entry["required"] = True
    if rules.get("allowed_values"):
        entry["allowed_values"] = list(rules["allowed_values"])
    if rules.get("min") is not None:
        entry["min"] = rules["min"]
    return entry


SPECS: Dict[str, Dict[str, Any]] = {
    capability_id: {
        "entity": cls.ENTITY,
        "fields": [
            _field(name, cls.CONSTRAINTS.get(name) or {}) for name in cls.FIELDS
        ],
    }
    for capability_id, cls in models.MODELS.items()
}

DEFAULT_CAPABILITY = "progress_claim_processing"


def sample_payload(capability_id: str) -> Dict[str, Any]:
    cls = models.MODELS[capability_id]
    payload: Dict[str, Any] = {}
    for name in cls.FIELDS:
        rules = cls.CONSTRAINTS.get(name) or {}
        if not rules.get("required"):
            continue
        allowed = rules.get("allowed_values")
        if allowed:
            payload[name] = allowed[0]
        elif str(rules.get("type")) in ("int",):
            payload[name] = int(rules.get("min") or 1)
        elif str(rules.get("type")) in ("float", "money", "quantity"):
            payload[name] = float(rules.get("min") or 1)
        else:
            payload[name] = "sample"
    return payload


SAMPLE: Dict[str, Any] = sample_payload(DEFAULT_CAPABILITY)


def install() -> None:
    """Copy the spec table onto the factory-owned domain_ops module."""
    from app import domain_ops

    domain_ops.SPECS.clear()
    domain_ops.SPECS.update(SPECS)
    domain_ops.DEFAULT_CAPABILITY = DEFAULT_CAPABILITY
    domain_ops.SAMPLE.clear()
    domain_ops.SAMPLE.update(SAMPLE)
