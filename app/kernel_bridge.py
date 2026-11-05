"""The kernel's view of a capability: an ActionSpec whose handler is the
capability's own handle(). The S12 outcomes run through execute_action, so
the domain decisions are the same code the HTTP route runs.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from app import jobs, models
from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)


def handler_module(capability_id: str):
    stem = str(capability_id).replace("-", "_")
    return importlib.import_module(f"app.actions.{stem}")


def _json_type(kind: str) -> str:
    return {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}.get(
        kind, "string"
    )


def input_schema(capability_id: str) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required = []
    for field in jobs.fields_for(capability_id):
        prop: Dict[str, Any] = {"type": _json_type(field["type"])}
        if field.get("allowed_values"):
            prop["enum"] = list(field["allowed_values"])
        properties[field["name"]] = prop
        if field.get("required"):
            required.append(field["name"])
    return {"type": "object", "properties": properties, "required": required}


async def _run(capability_id: str, context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
    module = handler_module(capability_id)
    payload = dict(arguments or {})
    payload.pop("capability_id", None)
    outcome = module.handle(payload, tenant_id=context.tenant_id)
    if not isinstance(outcome, dict):
        return ActionOutcome(
            status=ActionStatus.EXECUTION_ERROR,
            error_code="non_mapping",
            error_message=f"{capability_id} handle() did not answer a mapping",
        )
    if outcome.get("ok") is False:
        return ActionOutcome(
            status=ActionStatus.VALIDATION_ERROR,
            error_code="refused",
            error_message=str(outcome.get("error") or "refused"),
            output={"record": outcome.get("record")},
        )
    return ActionOutcome.success(
        {"record": outcome.get("record"), "result": outcome.get("result")}
    )


def spec_for(capability_id: str) -> ActionSpec:
    capability = jobs.capability(capability_id)
    if capability is None:
        raise ValueError(f"unknown capability: {capability_id}")

    async def handler(context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        return await _run(capability_id, context, arguments)

    return ActionSpec(
        action_id=f"product.{capability_id}",
        domain="product",
        name=capability_id,
        description=str(capability.get("summary") or capability_id),
        input_schema=input_schema(capability_id),
        output_schema={},
        required_context=[],
        permissions=["product.write"],
        read_only=False,
        handler=handler,
    )


def specs() -> Dict[str, Dict[str, Any]]:
    """The declaration app.domain_ops runs the S12 outcomes against."""
    out: Dict[str, Dict[str, Any]] = {}
    for capability_id in jobs.CAPABILITY_IDS:
        out[capability_id] = {
            "entity": models.entity_for(capability_id),
            "fields": jobs.fields_for(capability_id),
        }
    return out
