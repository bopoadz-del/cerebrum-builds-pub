"""Manager-only log-in and roles for the two Moroccan plants."""

from __future__ import annotations

import secrets
from typing import Any, Dict

from app.actions._common import block_failure, envelope, token_from_env
from app.dispatch import execute
from app.tenancy import current_tenant

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "manager_only_access"
ENTITY = "manager_only_access"
BLOCK_IDS = ["auth", "user_auth", "multi_tenant_rbac"]
BLOCK_DEFAULT_ACTIONS = {"auth": "validate", "user_auth": "register", "multi_tenant_rbac": "list_tenants"}

READS = [
    {"kind": "caller", "scope": "input"},
    {"kind": "env", "scope": "process"},
]
WRITES = [{"kind": "caller", "scope": "output"}]
NEVER = [{"kind": "network", "scope": "http.outbound"}]


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    email = str(record.get("manager_email") or "manager@example.com")
    role = str(record.get("role") or "manager")
    plant = str(record.get("plant") or "plant-casablanca")

    key = execute(
        "auth",
        {"api_key": token_from_env()},
        action=BLOCK_DEFAULT_ACTIONS.get("auth"),
    )
    refused = block_failure("auth", key)
    if refused:
        return refused

    registered = execute(
        "user_auth",
        {"email": email, "password": secrets.token_urlsafe(18)},
        action=BLOCK_DEFAULT_ACTIONS.get("user_auth"),
    )
    refused = block_failure("user_auth", registered)
    if refused:
        return refused

    tenants = execute(
        "multi_tenant_rbac",
        {"user_id": email, "tenant_id": current_tenant(), "plant": plant},
        action=BLOCK_DEFAULT_ACTIONS.get("multi_tenant_rbac"),
    )
    refused = block_failure("multi_tenant_rbac", tenants)
    if refused:
        return refused

    return envelope(
        {
            "manager_email": email,
            "role": role,
            "plant": plant,
            "manager_only": role == "manager",
            "login": {
                "method": "platform_bearer_token",
                "tenant_token_checked": bool(token_from_env()),
                "credential_store_checked": bool(key.get("valid")),
            },
            "registered": registered.get("status") == "ok",
            "credential_state": "provisional"
            if registered.get("status") == "ok"
            else "existing",
            "visible_tenants": tenants.get("tenants") or [],
            "visible_projects": tenants.get("projects") or [],
            "plant_scope": [plant] if plant else [],
        },
        record,
    )
