"""Bridge between the kernel's execute_action contract and the capability
handlers.

The kernel's ten business outcomes (create/read/update/delete/list, queue,
refusal, idempotency, authorization, missing-field) run through
``app.cerebrum_product_kernel.contract.runtime.execute_action``.  This module
gives that runtime one ActionSpec per capability, whose handler calls the
capability's own ``handle()`` -- the same function the HTTP route calls.

No block, no tenant and no persistence decision lives here: the handler is
pure dispatch, and the route (or the kernel's own create op) persists.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Dict, List

from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)

DOMAIN = __name__.split(".")[0]
ACTIONS_PACKAGE = "app.actions"
_OK = "ok"
_ERROR = "error"

logger = logging.getLogger(__name__)

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def module_name(capability_id: str) -> str:
    return str(capability_id or "").replace("-", "_")


def model_for(capability_id: str):
    from app.models import MODELS

    name = module_name(capability_id)
    model = MODELS.get(name)
    if model is None:
        raise ValueError("unknown capability_id: %r" % capability_id)
    return model


def declared_field_names(capability_id: str) -> List[str]:
    return [str(name) for name in (getattr(model_for(capability_id), "FIELDS", ()) or ())]


def input_schema(capability_id: str) -> Dict[str, Any]:
    model = model_for(capability_id)
    constraints = getattr(model, "CONSTRAINTS", {}) or {}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name in declared_field_names(capability_id):
        rule = constraints.get(name) or {}
        prop: Dict[str, Any] = {"type": str(rule.get("type") or "string")}
        allowed = list(rule.get("allowed_values") or ())
        if allowed:
            prop["enum"] = allowed
        properties[name] = prop
        if rule.get("required"):
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _handler_for(capability_id: str) -> Any:
    name = module_name(capability_id)
    accepted = tuple(declared_field_names(capability_id))

    async def handler(_context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        module = importlib.import_module("%s.%s" % (ACTIONS_PACKAGE, name))
        payload = {field: arguments[field] for field in accepted if field in arguments}
        try:
            out = module.handle(payload)
            if inspect.isawaitable(out):
                out = await out
        except Exception as exc:  # one typed outcome, no leakage
            logger.exception("capability '%s' handler raised", name)
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="capability_error",
                error_message="%s: the capability failed to execute" % type(exc).__name__,
            )
        if not isinstance(out, dict):
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="invalid_handler_result",
                error_message="capability '%s' returned %s, not a mapping"
                % (name, type(out).__name__),
            )
        if out.get(_OK) is False:
            return ActionOutcome(
                status=ActionStatus.VALIDATION_ERROR,
                error_code="capability_refused",
                error_message=str(out.get(_ERROR) or "capability refused"),
                output=dict(out),
            )
        return ActionOutcome(status=ActionStatus.SUCCESS, output=dict(out))

    return handler


def spec_for(capability_id: str) -> ActionSpec:
    from app.domain_ops import PROCESS_PERMISSION

    name = module_name(capability_id)
    model = model_for(name)
    doc = (getattr(model, "__doc__", "") or "").strip().splitlines()
    return ActionSpec(
        action_id="%s.%s" % (DOMAIN, name),
        domain=DOMAIN,
        name=name,
        description=doc[0] if doc else "%s capability" % name,
        input_schema=input_schema(name),
        output_schema={},
        required_context=["tenant_id"],
        permissions=[PROCESS_PERMISSION],
        read_only=False,
        handler=_handler_for(name),
    )
