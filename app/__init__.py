"""Cerebrum product package.

Importing the package registers each capability's declared contract with
the S12 domain-ops kernel so both the HTTP surface and the kernel runtime
execute the same handlers.
"""

from __future__ import annotations

from typing import Any, Dict


def _register_domain_specs() -> None:
    from app import domain_ops
    from app.models import MODELS

    for capability_id, cls in MODELS.items():
        fields = []
        for name in cls.FIELDS:
            rules = dict(cls.CONSTRAINTS.get(name) or {})
            kind = cls.FIELD_TYPES.get(name, "str")
            mapped = {
                "money": "float",
                "quantity": "int",
                "date": "str",
                "email": "str",
            }.get(kind, kind)
            fields.append(
                {
                    "name": name,
                    "type": mapped,
                    "required": bool(rules.get("required")),
                    "allowed_values": list(rules.get("allowed_values") or []),
                    "min": rules.get("min"),
                    "max": rules.get("max"),
                }
            )
        domain_ops.SPECS[capability_id] = {
            "entity": getattr(cls, "ENTITY", capability_id),
            "fields": fields,
        }

    default = "document_grounded_qa"
    domain_ops.DEFAULT_CAPABILITY = default
    domain_ops.DEFAULT_ENTITY = default
    domain_ops.SAMPLE = domain_ops.sample_payload(default)


_register_domain_specs()
