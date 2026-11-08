"""Bridge between this product's capabilities and the kernel contract runtime.

``domain_ops`` performs the S12 outcomes (create/read/update/delete/list/
enqueue/process/refuse) through ``execute_action``. It ships with an empty
registry so it carries no product knowledge; this module binds the product's
capabilities onto it, and exposes the one ActionSpec the queue's ``process``
operation runs.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app import sources
from app.models import MODELS
from app.validation import sample_for_model

DEFAULT_CAPABILITY_ENV = "PRODUCT_DEFAULT_CAPABILITY"


def default_capability() -> str:
    """The capability the kernel's S12 drill performs (first answerable one)."""
    from app.placeholders import PLACEHOLDER_CONNECTORS

    for cap in MODELS:
        if not PLACEHOLDER_CONNECTORS.get(cap):
            return cap
    return next(iter(MODELS), "")


def _field_rows(cls) -> List[Dict[str, Any]]:
    constraints = getattr(cls, "CONSTRAINTS", {}) or {}
    rows: List[Dict[str, Any]] = []
    for name in cls.FIELDS:
        spec = dict(constraints.get(name) or {})
        declared = str(spec.get("type", "str"))
        # The kernel's schema vocabulary is string/integer/number/boolean;
        # money and quantity are numeric domain aliases.
        if declared in ("money", "quantity"):
            declared = "float"
        row: Dict[str, Any] = {"name": name, "type": declared}
        for key in ("required", "allowed_values", "min", "max", "format", "max_length"):
            if key in spec:
                row[key] = spec[key]
        rows.append(row)
    return rows


def bind_domain_ops() -> None:
    """Declare this product's capabilities to ``app.domain_ops``.</br>

    Idempotent: called from the package import, so the kernel's S12 path is
    bound before any route can reach it.
    """
    from app import domain_ops

    for capability_id, cls in MODELS.items():
        domain_ops.SPECS[capability_id] = {
            "entity": cls.ENTITY,
            "fields": _field_rows(cls),
            "label": capability_id.replace("_", " ").title(),
        }
    chosen = default_capability()
    if chosen:
        domain_ops.DEFAULT_CAPABILITY = chosen
        domain_ops.DEFAULT_ENTITY = MODELS[chosen].ENTITY
        domain_ops.SAMPLE = sample_for_model(MODELS[chosen])


def _input_schema(cls) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        "capability_id": {"type": "string"},
        "idempotency_key": {"type": "string"},
    }
    for row in _field_rows(cls):
        prop: Dict[str, Any] = {"type": "string"}
        ftype = row.get("type")
        if ftype == "int":
            prop = {"type": "integer"}
        elif ftype in ("float", "money", "quantity"):
            prop = {"type": "number"}
        elif ftype == "bool":
            prop = {"type": "boolean"}
        if row.get("allowed_values"):
            prop["enum"] = list(row["allowed_values"])
        properties[row["name"]] = prop
    return {"type": "object", "properties": properties, "required": []}


async def _run_capability(context, arguments: Dict[str, Any]):
    """Run a stored queue payload through the capability's own handler."""
    import importlib

    from app.cerebrum_product_kernel.contract.models import ActionOutcome

    capability_id = str(arguments.get("capability_id") or "")
    module_name = "app.actions." + capability_id.replace("-", "_")
    try:
        module = importlib.import_module(module_name)
    except Exception:  # noqa: BLE001 - an unknown capability is a refusal
        return ActionOutcome(
            status="validation_error",
            error_code="unknown_capability",
            error_message=f"unknown capability: {capability_id}",
        )
    payload = {k: v for k, v in (arguments or {}).items() if k != "idempotency_key"}
    try:
        result = module.handle(payload)
    except Exception as exc:  # noqa: BLE001 - never leak a stack trace
        return ActionOutcome(
            status="execution_error",
            error_code="handler_exception",
            error_message=f"{type(exc).__name__}: the capability handler raised",
        )
    if not isinstance(result, dict) or result.get("ok") is not True:
        return ActionOutcome(
            status="validation_error",
            error_code="capability_refused",
            error_message=str((result or {}).get("error") or "the capability refused"),
        )
    return ActionOutcome.success(
        {
            "capability_id": capability_id,
            "entity": MODELS[capability_id].ENTITY if capability_id in MODELS else capability_id,
            "result": result.get("result"),
            "authority": result.get("authority"),
        }
    )


def spec_for(capability_id: str):
    """The kernel ActionSpec for one capability (used by queue ``process``)."""
    from app.cerebrum_product_kernel.contract.models import ActionSpec

    cls = MODELS.get(capability_id)
    if cls is None:
        from app import domain_ops

        return domain_ops.spec_for_op("create", capability_id)
    return ActionSpec(
        action_id=f"{sources.PRODUCT_ID}.run_capability",
        domain=sources.PRODUCT_ID,
        name=capability_id,
        description=f"Run the {capability_id} capability over a stored payload.",
        input_schema=_input_schema(cls),
        output_schema={},
        required_context=[],
        permissions=[f"{sources.PRODUCT_ID}.process"],
        read_only=False,
        handler=_run_capability,
    )
