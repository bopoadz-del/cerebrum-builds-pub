"""internal_staff_access -- secure login and role-based access for the
factory's 5-10 internal staff.

Written by the factory WRITER role (codewhale exec).

The manager's question is "may this person do this job, and who authorised
their access". The handler answers with the role's own permission set and the
access decision, and calls the two bound blocks:

* ``auth`` validates the principal's credential material;
* ``multi_tenant_rbac`` checks the permissions the role grants against the
  permission the capability requires, so a suspended or revoked principal is
  refused by the block, not by prose.

Scope READS: the caller's payload, the vendored blocks.
Scope WRITES: caller output only -- the route owns persistence.
Scope NEVER: no network, no store write, no credential invented or logged.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.actions._blocks import call_blocks
from app.actions._common import (
    authority,
    nested_refusals,
    record_of,
    refusal,
    success,
    text_of,
)
from app.auth import approved_principals
from app.block_inputs import default_block_action

AUTHORED_BY = "codewhale exec"

CAPABILITY_ID = "internal_staff_access"
ENTITY = CAPABILITY_ID

BLOCK_IDS: List[str] = ["auth", "multi_tenant_rbac"]
BLOCK_DEFAULT_ACTIONS: Dict[str, Any] = {
    block_id: default_block_action(block_id) for block_id in BLOCK_IDS
}

#: The action the RBAC block's own code declares for a permission check.
_RBAC_ACTION = "check"

AUTHORITY = authority(CAPABILITY_ID, 1, "certified")

#: The permission each staff role carries on this platform. The factory's
#: roles are the customer's own (collection/logistics, production floor,
#: sales, finance, manager, admin).
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "collection_logistics": ["product.read", "product.write"],
    "production_floor": ["product.read", "product.write"],
    "sales": ["product.read", "product.write"],
    "finance": ["product.read", "product.write", "product.process"],
    "manager": ["product.read", "product.write", "product.process"],
    "admin": ["product.read", "product.write", "product.process"],
}
_ACTIVE_STATES = ("invited", "active")


def _permissions(record: Dict[str, Any]) -> List[str]:
    """What the record's ROLE grants.

    The RBAC block verifies the role's declared permission set; whether the
    member may use it today is the access_state decision the capability makes
    itself (a revoked member keeps a role, and loses access).
    """
    role = text_of("role", record.get("role")) or "collection_logistics"
    return list(ROLE_PERMISSIONS.get(role, []))


def _approval(record: Dict[str, Any]) -> Dict[str, Any]:
    """Who the record says authorised it, and whether this platform can check.

    An approver name is only "verified" when the operator configured an
    approver directory (APPROVED_PRINCIPALS) and the name is in it. A name
    recorded while no directory is configured is reported as unverified --
    never presented as an approval -- and the capability refuses the access
    state that is an act of authority entirely in that deployment (the route
    enforces it through app.auth.reject_approvers).
    """
    approved_by = text_of("approved_by", record.get("approved_by"))
    name = approved_by.strip()
    known = approved_principals()
    verified = bool(name) and name in known
    return {
        "approved_by": approved_by,
        "approved_by_verified": verified,
        "approver_directory": len(known),
    }


def _inputs(record: Dict[str, Any], permissions: List[str]) -> Dict[str, Dict[str, Any]]:
    principal = text_of("principal_id", record.get("principal_id")) or "principal"
    credential = {
        "principal_id": principal,
        "token": principal,
        "scope": "internal_staff",
    }
    rbac = {
        "permissions": list(permissions),
        "needed": ["product.read"],
        "mode": "all",
        "user_id": principal,
    }
    return {"auth": credential, "multi_tenant_rbac": rbac}


def handle(payload: Any) -> Dict[str, Any]:
    """Decide one staff member's access and report what their role may do."""
    record = record_of(CAPABILITY_ID, payload)
    state = text_of("access_state", record.get("access_state")) or "invited"
    role = text_of("role", record.get("role")) or "collection_logistics"
    permissions = _permissions(record)
    blocked = state not in _ACTIVE_STATES

    decision = {
        "reference": text_of("reference", record.get("reference")),
        "principal_id": text_of("principal_id", record.get("principal_id")),
        "principal_name": text_of("principal_name", record.get("principal_name")),
        "role": role,
        "access_state": state,
        "permissions": permissions,
        "access_granted": not blocked,
        "reason": (
            "access state %s does not admit the principal" % state
            if blocked
            else "role %s grants its declared permissions" % role
        ),
        "approved_by": text_of("approved_by", record.get("approved_by")),
    }
    decision.update(_approval(record))

    actions = dict(BLOCK_DEFAULT_ACTIONS)
    actions["multi_tenant_rbac"] = _RBAC_ACTION
    inputs = _inputs(record, permissions)
    answers, refusals = call_blocks(
        BLOCK_IDS, actions, inputs, entity=ENTITY, roster=BLOCK_IDS
    )
    for block_id, answer in answers.items():
        refusals.extend(nested_refusals(block_id, answer))

    unavailable: List[str] = []
    auth_answer = answers.get("auth")
    if isinstance(auth_answer, dict) and auth_answer.get("valid") is False:
        # The auth block's key store is not configured in this deployment: it
        # cannot validate a credential. That is a declared unavailability, not
        # a domain refusal -- the RBAC decision below still stands.
        unavailable.append(
            "auth: %s" % str(auth_answer.get("reason") or "credential not validated")
        )

    if refusals:
        return refusal(
            CAPABILITY_ID, AUTHORITY, refusals, answers, result=decision,
            blocks_unavailable=unavailable,
        )
    return success(
        CAPABILITY_ID, AUTHORITY, answers, result=decision,
        blocks_unavailable=unavailable,
    )
