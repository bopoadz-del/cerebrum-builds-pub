"""Bridge capability handle() through the vendored product kernel.

The kernel owns trust-scope, input/output validation, and ActionResult.
Persistence stays in the HTTP route after ActionStatus.SUCCESS.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple

from app.cerebrum_product_kernel.contract.models import (
    ActionContext,
    ActionOutcome,
    ActionSpec,
    ActionStatus,
)
from app.cerebrum_product_kernel.contract.runtime import execute_action


def _wrap_handle(handle):
    async def _handler(context: ActionContext, arguments: Dict[str, Any]) -> ActionOutcome:
        # Live invoice-management (2026-08-30): a coder handler returned
        # ok:True after execute() failed. Without watching the seam, this
        # wrapper treated that as ActionStatus.SUCCESS and the route
        # persisted. A capability route must not report success over a
        # failed block, whichever path wrote the handler.
        import sys
        import app.dispatch as _dispatch

        _real = _dispatch.execute
        _failed = []

        def _watched(block_id, *a, **kw):
            res = _real(block_id, *a, **kw)
            if isinstance(res, dict) and (
                res.get("status") == "error" or "error" in res
            ):
                _failed.append(str(block_id))
            return res

        _dispatch.execute = _watched
        _patched = []
        for _name, _mod in list(sys.modules.items()):
            if _name.startswith("app.actions") and hasattr(_mod, "execute"):
                _patched.append((_mod, _mod.execute))
                _mod.execute = _watched
        try:
            out = handle(arguments)
        finally:
            _dispatch.execute = _real
            for _mod, _prev in _patched:
                _mod.execute = _prev
        if not isinstance(out, dict):
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="invalid_handler_result",
                error_message="handle() returned a non-mapping",
            )
        if out.get("ok") is False:
            return ActionOutcome(
                status=ActionStatus.VALIDATION_ERROR,
                error_code="refused",
                error_message=str(out.get("error") or "refused"),
                output=out,
            )
        if _failed:
            return ActionOutcome(
                status=ActionStatus.EXECUTION_ERROR,
                error_code="block_failed",
                error_message="block(s) failed: " + ", ".join(_failed),
                output=out,
            )
        return ActionOutcome.success(out)

    return _handler


def spec_for(capability_id: str) -> ActionSpec:
    name = capability_id.replace("-", "_")
    mod = importlib.import_module(f"app.actions.{name}")
    return ActionSpec(
        action_id=f"product.{name}",
        domain="product",
        name=name,
        description=str(getattr(mod, "CAPABILITY_ID", name)),
        # The capability's own domain columns. Without them the kernel strips
        # any column named like a trust-scope key -- project_id, user_id,
        # tenant_id -- and the handler refuses its own well-formed payload.
        input_schema={
            "properties": {
                str(f): {} for f in (getattr(mod, "CAPABILITY_FIELDS", ()) or ())
            }
        },
        output_schema={},
        required_context=[],
        permissions=[],
        read_only=False,
        handler=_wrap_handle(mod.handle),
    )


#: Tenancy speaks in roles; the kernel checks permissions. A role name is not
#: a permission: passing roles straight through left every caller holding
#: ["admin"] against operation specs that require product.write, so every
#: PUT and DELETE in every generated platform answered permission_denied
#: (13/13 in Docker -- no check wrote twice).
#: Unknown roles grant nothing.
ROLE_PERMISSIONS: Dict[str, Tuple[str, ...]] = {
    "admin": ("product.read", "product.write", "product.process"),
    "writer": ("product.read", "product.write"),
    "reader": ("product.read",),
}


def permissions_for_roles(roles) -> List[str]:
    granted: List[str] = []
    for role in roles or ():
        for permission in ROLE_PERMISSIONS.get(str(role), ()):
            if permission not in granted:
                granted.append(permission)
    return granted


def product_context(request) -> ActionContext:
    """Build the kernel ActionContext from the authenticated principal.

    The tenant is resolved from the request's bearer token by
    app.tenancy.resolve_tenant — the single resolution path shared with
    rag_routes. A caller that cannot be bound to a tenant is refused by
    name (401 authentication_required), never mapped to a default.
    """
    import app.tenancy as tenancy
    from fastapi import HTTPException

    try:
        tenant = tenancy.resolve_tenant(request.headers)
    except tenancy.TenantRefused:
        raise HTTPException(status_code=401, detail="authentication_required")
    return ActionContext(
        user_id=tenant.tenant_id,
        tenant_id=tenant.tenant_id,
        organisation_id=tenant.tenant_id,
        project_id=tenant.tenant_id,
        permissions=permissions_for_roles(getattr(tenant, "roles", ())),
        allowed_domains=["product"],
    )


async def run_capability(capability_id: str, payload: Dict[str, Any], request) -> Dict[str, Any]:
    result = await execute_action(spec_for(capability_id), product_context(request), payload or {})
    return result.to_dict()
