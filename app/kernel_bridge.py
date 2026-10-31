"""Bridge a capability handler into the kernel's ActionSpec runtime.

The S12 domain outcomes run through app.cerebrum_product_kernel.contract
rather than through a bespoke route, so the queue processor and the HTTP
surface execute the same handler.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)


def _handler_for(capability_id: str):
    module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))

    async def _run(_context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        payload = {k: v for k, v in (arguments or {}).items() if k != "capability_id"}
        outcome = module.handle(payload)
        if not isinstance(outcome, dict):
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="invalid_handler_answer",
                error_message="handler did not return a mapping",
            )
        if outcome.get("ok") is False:
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="handler_refused",
                error_message=str(outcome.get("error") or "handler refused"),
                output={"result": outcome.get("result") or {}},
            )
        return ActionOutcome.success({"result": outcome.get("result") or {}, "record": outcome.get("record") or {}})

    return _run


def spec_for(capability_id: str) -> ActionSpec:
    return ActionSpec(
        action_id=f"product.{capability_id}",
        domain="product",
        name=capability_id,
        description=f"Run the {capability_id} capability",
        input_schema={},
        output_schema={},
        required_context=[],
        permissions=["product.process"],
        read_only=False,
        handler=_handler_for(capability_id),
    )
