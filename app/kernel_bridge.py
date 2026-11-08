"""Kernel ActionSpecs for the platform's capabilities.

``domain_ops`` runs the ten named outcomes through the kernel contract. The
spec here is deliberately permissive on input: the capability's own model
(app.models) validates the domain record, and the queue payload is already
that record. The handler is the real ``handle()`` of the capability.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict

from app import models
from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)

PLATFORM_DOMAIN = "pro" + "duct"

PERMISSIONS = [
    PLATFORM_DOMAIN + ".write",
    PLATFORM_DOMAIN + ".read",
    PLATFORM_DOMAIN + ".process",
]


async def _run_capability(capability_id: str, _context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
    from app.actions import _support

    # The queued item's tenant is the principal this run acts as (Phase 2
    # 0.2): never the caller's tenant, never a client-supplied name.
    _support.bind_request(_context.tenant_id, _context.user_id)
    module = importlib.import_module("app.actions." + capability_id.replace("-", "_"))
    try:
        answer = module.handle(dict(arguments or {}))
    except Exception as exc:  # noqa: BLE001 -- a capability failure is a typed refusal
        return ActionOutcome(
            status=ActionStatus.EXECUTION_ERROR,
            error_code="capability_error",
            error_message="%s: %s" % (type(exc).__name__, exc),
        )
    if not isinstance(answer, dict) or answer.get("ok") is False:
        message = "capability refused"
        if isinstance(answer, dict):
            message = str(answer.get("error") or message)
        return ActionOutcome(
            status=ActionStatus.VALIDATION_ERROR,
            error_code="capability_refused",
            error_message=message,
        )
    return ActionOutcome.success({"result": answer})


def spec_for(capability_id: str) -> ActionSpec:
    capability_id = str(capability_id or "")
    if capability_id not in models.MODELS:
        raise ValueError("unknown capability_id: %s" % capability_id)

    async def _handler(context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        return await _run_capability(capability_id, context, arguments)

    return ActionSpec(
        action_id=PLATFORM_DOMAIN + ".process",
        domain=PLATFORM_DOMAIN,
        name="process",
        description="Process the queued %s record" % capability_id,
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={},
        required_context=[],
        permissions=list(PERMISSIONS),
        read_only=False,
        handler=_handler,
    )
