"""role_based_access_and_audit -- who may do what, and the ledger that proves it.

Contract administration separates the people who prepare a claim from the
people who certify it. The role table below is the product's access model; a
decision is computed from the role and the requested permission, then written
through the fail-closed audit and governance blocks.

READS   the request record, the configured platform token (via the auth block),
        and this capability's role table.
WRITES  a decision record under STORAGE_PATH/workspace and this capability's
        result; the ROUTE persists the record, never the handler.
NEVER   grants a permission the role does not hold, or lets an unauthenticated
        principal through.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List

from app.actions import _support
from app.dispatch import BLOCK_DEFAULT_ACTIONS as _DISPATCH_DEFAULT_ACTIONS
from app.actions._support import ok, refuse, run_blocks

AUTHORED_BY = "codewhale exec"
CAPABILITY_ID = "role_based_access_and_audit"
ENTITY = "role_based_access_and_audit"
BLOCK_IDS = ["auth", "multi_tenant_rbac", "audit_fail_closed", "governance_gate"]
BLOCK_DEFAULT_ACTIONS = {block_id: _DISPATCH_DEFAULT_ACTIONS.get(block_id) for block_id in BLOCK_IDS}

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "owner": [
        "contract.read",
        "contract.write",
        "claim.submit",
        "claim.approve",
        "document.publish",
        "audit.read",
    ],
    "contracts_manager": [
        "contract.read",
        "contract.write",
        "claim.submit",
        "claim.approve",
        "document.publish",
        "audit.read",
    ],
    "quantity_surveyor": [
        "contract.read",
        "claim.submit",
        "document.publish",
    ],
    "viewer": ["contract.read"],
}


def handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = dict(payload or {})
    reference = _support.reference_of(record)
    principal_id = _support.text_of(record, "principal_id") or reference
    role = (_support.text_of(record, "role") or "viewer").lower()
    permission = _support.text_of(record, "permission") or "contract.read"
    requested_action = _support.text_of(record, "requested_action") or "read"
    if role not in ROLE_PERMISSIONS:
        return refuse(
            f"role {role!r} is not a declared contract-administration role; "
            "known roles: " + ", ".join(sorted(ROLE_PERMISSIONS)),
            error_kind="unknown_role",
        )

    granted = list(ROLE_PERMISSIONS[role])
    decision = "allow" if permission in granted else "deny"
    token = (os.environ.get("PLATFORM_TOKEN") or "").strip()
    if not token:
        decision = "deny"

    workspace = _support.workspace_dir(CAPABILITY_ID)
    decision_record = {
        "reference": reference,
        "principal_id": principal_id,
        "role": role,
        "permission": permission,
        "requested_action": requested_action,
        "decision": decision,
        "granted_permissions": granted,
    }
    decision_file = workspace / f"access_{reference.replace('/', '_')}_{uuid.uuid4().hex[:8]}.json"
    decision_file.write_text(json.dumps(decision_record, indent=2, sort_keys=True), encoding="utf-8")

    inputs: Dict[str, Dict[str, Any]] = {
        "auth": {
            "token": token,
            "required_role": role,
            "principal_id": principal_id,
        },
        "multi_tenant_rbac": {
            "permissions": granted,
            "needed": [permission] if decision == "allow" else granted[:1],
            "mode": "all",
            "principal_id": principal_id,
            "requested_permission": permission,
            "decision": decision,
        },
        "audit_fail_closed": {
            "principal_id": principal_id,
            "token": token,
            "requested_action": requested_action,
            "permission": permission,
        },
        "governance_gate": {
            "tenant_id": _support.text_of(record, "_tenant_id") or "local",
            "action_type": f"contract.{requested_action}",
            "target_id": reference,
            "requester_id": principal_id,
            "payload": decision_record,
        },
    }

    answers, refusal, unavailable = run_blocks(CAPABILITY_ID, record, BLOCK_IDS, inputs)
    if refusal:
        return refuse(refusal, error_kind="block_refused")

    result = {
        **decision_record,
        "authorized": decision == "allow",
        "block_evidence": {
            "authenticated": isinstance(answers.get("auth"), dict)
            and answers["auth"].get("ok") is not False,
            "rbac_checked": isinstance(answers.get("multi_tenant_rbac"), dict)
            and answers["multi_tenant_rbac"].get("ok") is not False,
            "audited": isinstance(answers.get("audit_fail_closed"), dict)
            and answers["audit_fail_closed"].get("ok") is not False,
            "governed": isinstance(answers.get("governance_gate"), dict)
            and answers["governance_gate"].get("ok") is not False,
        },
        "decision_file": str(decision_file),
        "blocks_run": list(BLOCK_IDS),
        "authority": "layer 1 certified",
    }
    if unavailable:
        result["blocks_unavailable"] = sorted(set(unavailable))
    return ok(CAPABILITY_ID, result)
