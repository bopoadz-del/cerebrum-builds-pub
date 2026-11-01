"""Bridge between this platform's capabilities and the vendored kernel.

The persisted work queue processes an item by running the capability the
item names through ``execute_action`` -- the same kernel path every product
action takes. This module is the one place that turns a capability id into
an :class:`ActionSpec`:

* the spec's declared input schema is built from the capability's own
  declaration in ``app.models`` (``FIELDS`` + ``CONSTRAINTS``) -- the same
  schema the route enforces, never a second, stricter contract;
* the spec's handler is the capability's own ``app.actions.<capability>``
  module, called with exactly the declared record fields.

Nothing here names a capability, a field or a case: the mapping is the
platform's own roster, read at call time.

Authority: a capability action reached through this bridge is executed on
behalf of the queue that already claimed the item, so the one permission it
requires is the authority to process queued work -- checked once, at the
edge of the ``process`` op, and again here by the kernel. The queue item
carries its own tenant, and that tenant is the context the capability runs
as; a caller's context is never forwarded.

Scope READS: the product's declared models, the capability's own module.
Scope WRITES: caller output only -- nothing is persisted here.
Scope NEVER: no network, no store write, no record invented for a payload
the caller did not send.
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

AUTHORED_BY = "codewhale exec"

#: The domain every capability of this platform acts in.
DOMAIN = "product"
#: Where the platform's capability handlers live.
ACTIONS_PACKAGE = "app.actions"

_OK = "ok"
_ERROR = "error"

#: Python declaration -> JSON Schema type. Read from the model annotation.
_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}

logger = logging.getLogger(__name__)


def module_name(capability_id: str) -> str:
    """The capability's module/id spelling: '-' and '.' normalise to '_'."""
    name = str(capability_id or "").strip().replace("-", "_").replace(".", "_")
    if not name:
        raise ValueError("capability_id is required")
    return name


def model_for(capability_id: str) -> Any:
    """The capability's declared model class from the product's roster."""
    from app.models import MODELS

    name = module_name(capability_id)
    model = MODELS.get(name)
    if model is None:
        raise ValueError(f"unknown capability_id: {capability_id!r}")
    return model


def declared_field_names(capability_id: str) -> List[str]:
    return [str(name) for name in (getattr(model_for(capability_id), "FIELDS", ()) or ())]


def _field_type(model: Any, name: str) -> str:
    annotations = getattr(model, "__annotations__", {}) or {}
    return _JSON_TYPES.get(annotations.get(name), "string")


def input_schema(capability_id: str) -> Dict[str, Any]:
    """The capability's declared input schema, from its own model.

    The same source the route validates against: ``FIELDS`` give the
    properties and their types, ``CONSTRAINTS`` give the vocabularies and
    the required set. A field that needs a vocabulary declares it there.
    """
    model = model_for(capability_id)
    constraints = getattr(model, "CONSTRAINTS", {}) or {}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name in declared_field_names(capability_id):
        rule = constraints.get(name) or {}
        prop: Dict[str, Any] = {"type": str(rule.get("type") or _field_type(model, name))}
        allowed = list(rule.get("allowed_values") or ())
        if allowed:
            prop["enum"] = allowed
        properties[name] = prop
        if rule.get("required"):
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _handler_for(capability_id: str) -> Any:
    """The capability's own handler, adapted to the kernel's handler contract."""
    name = module_name(capability_id)
    accepted = tuple(declared_field_names(capability_id))

    async def handler(_context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        module = importlib.import_module(f"{ACTIONS_PACKAGE}.{name}")
        payload = {field: arguments[field] for field in accepted if field in arguments}
        try:
            out = module.handle(payload)
            if inspect.isawaitable(out):
                out = await out
        except Exception as exc:  # noqa: BLE001 - one typed outcome, no leakage
            logger.exception("capability '%s' handler raised", name)
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="capability_error",
                error_message=f"{type(exc).__name__}: the capability failed to execute",
            )
        if not isinstance(out, dict):
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="invalid_handler_result",
                error_message=(
                    f"capability '{name}' returned {type(out).__name__}, not a mapping"
                ),
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
    """The kernel spec for one capability of this platform."""
    from app.domain_ops import PROCESS_PERMISSION

    name = module_name(capability_id)
    model = model_for(name)
    model_doc = (getattr(model, "__doc__", "") or "").strip().splitlines()
    return ActionSpec(
        action_id=f"{DOMAIN}.{name}",
        domain=DOMAIN,
        name=name,
        description=model_doc[0] if model_doc else f"{name} for the Claims Platform",
        input_schema=input_schema(name),
        output_schema={},
        required_context=["tenant_id"],
        permissions=[PROCESS_PERMISSION],
        read_only=False,
        handler=_handler_for(name),
    )
