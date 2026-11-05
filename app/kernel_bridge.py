"""Bridge from a queued capability id to the kernel ActionSpec that runs it."""

from __future__ import annotations

import importlib
from typing import Any, Dict

from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)


def _handler(capability_id: str):
    async def run(_context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))
        result = module.handle(dict(arguments or {}))
        if not isinstance(result, dict):
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="no_result",
                error_message="capability returned no result",
            )
        if result.get("ok") is False:
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code=str(result.get("error_kind") or "refused"),
                error_message=str(result.get("error") or "capability refused"),
                output=result,
            )
        return ActionOutcome.success(result)

    return run


def spec_for(capability_id: str) -> ActionSpec:
    capability_id = str(capability_id)
    return ActionSpec(
        action_id="product.process",
        domain="product",
        name="process",
        description="Process a queued %s record" % capability_id,
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={},
        required_context=[],
        permissions=["product.process"],
        read_only=False,
        handler=_handler(capability_id),
    )
