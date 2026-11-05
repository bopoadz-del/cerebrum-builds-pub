"""Kernel ActionSpec bridge for queued capability execution.

The queue stores a payload; processing runs the same handler the HTTP route
runs, under the tenant recorded on the queue item. It does not persist a new
record -- persistence is the route's job.
"""

from __future__ import annotations

import importlib

from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)


def _module(capability_id: str):
    return importlib.import_module("app.actions." + str(capability_id).replace("-", "_"))


async def _handle(context: ActionContext, arguments: dict) -> ActionOutcome:
    capability_id = str(arguments.get("capability_id") or arguments.get("_capability_id") or "")
    if not capability_id:
        return ActionOutcome(
            status=ActionStatus.VALIDATION_ERROR,
            error_code="unknown_capability",
            error_message="capability_id is required",
        )
    payload = {k: v for k, v in arguments.items() if not k.startswith("_") and k != "capability_id"}
    try:
        result = _module(capability_id).handle(payload)
    except Exception as exc:  # noqa: BLE001 -- a failed job is a failed outcome
        return ActionOutcome(
            status=ActionStatus.EXECUTION_ERROR,
            error_code="handler_raised",
            error_message=f"{type(exc).__name__}: {exc}",
        )
    if not isinstance(result, dict) or result.get("ok") is False:
        return ActionOutcome(
            status=ActionStatus.VALIDATION_ERROR,
            error_code="capability_refused",
            error_message=str((result or {}).get("error") or "capability refused"),
            output=result if isinstance(result, dict) else {},
        )
    return ActionOutcome.success(result)


def spec_for(capability_id: str) -> ActionSpec:
    return ActionSpec(
        action_id="product.process",
        domain="product",
        name="process",
        description="Process one queued " + str(capability_id) + " payload",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={},
        required_context=[],
        permissions=["product.process"],
        read_only=False,
        handler=_handle,
    )
