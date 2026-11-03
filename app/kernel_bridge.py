"""Kernel bridge: declare the capability specs the domain ops execute.

domain_ops.SPECS drives create/read/update/delete/queue/idempotency/
refusal/unauthorized/missing-field through the kernel's execute_action.
The declarations here are generated from app.models so the schema the
kernel validates is the schema the HTTP route validates.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models import MODELS, sample_payload

DEFAULT_CAPABILITY = "claim_evidence_and_approvals"

_TYPE_NAMES = {int: "int", float: "float", bool: "bool", str: "str"}


def _fields(capability_id: str) -> List[Dict[str, Any]]:
    cls = MODELS[capability_id]
    constraints = cls.CONSTRAINTS or {}
    out: List[Dict[str, Any]] = []
    for name in cls.FIELDS:
        hint = type(getattr(cls, name, ""))
        field = {"name": name, "type": _TYPE_NAMES.get(hint, "str")}
        rules = constraints.get(name) or {}
        if rules.get("allowed_values"):
            field["allowed_values"] = list(rules["allowed_values"])
        if rules.get("required"):
            field["required"] = True
        if "min" in rules:
            field["min"] = rules["min"]
        out.append(field)
    return out


def specs() -> Dict[str, Dict[str, Any]]:
    return {
        capability_id: {
            "entity": cls.ENTITY,
            "fields": _fields(capability_id),
            "sample": sample_payload(capability_id),
        }
        for capability_id, cls in MODELS.items()
    }


def configure() -> None:
    from app import domain_ops

    domain_ops.SPECS.clear()
    domain_ops.SPECS.update(specs())
    domain_ops.DEFAULT_CAPABILITY = DEFAULT_CAPABILITY
    domain_ops.DEFAULT_ENTITY = MODELS[DEFAULT_CAPABILITY].ENTITY
    domain_ops.SAMPLE = sample_payload(DEFAULT_CAPABILITY)


def spec_for(capability_id: str):
    from app.cerebrum_product_kernel.contract.models import (
        ActionOutcome, ActionSpec, ActionStatus,
    )
    from app.domain_ops import PROCESS_PERMISSION
    import importlib

    async def _handler(_context, arguments):
        module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))
        result = module.handle(dict(arguments))
        if not isinstance(result, dict) or result.get("ok") is not True:
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="capability_refused",
                error_message=str((result or {}).get("error") or "refused"),
            )
        return ActionOutcome.success({"result": result})

    return ActionSpec(
        action_id=f"product.execute_{capability_id}",
        domain="product",
        name="execute",
        description=f"execute the {capability_id} capability",
        input_schema={},
        output_schema={},
        required_context=[],
        permissions=[PROCESS_PERMISSION],
        read_only=False,
        handler=_handler,
    )
