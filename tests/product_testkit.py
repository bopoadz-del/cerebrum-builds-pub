"""Test helpers for the product suites (not a test module).

``stub_blocks`` replaces the block boundary with a well-formed success
envelope so a route test measures the product's own path -- validation, the
handler's decisions, the tenant-scoped write, the read-back -- without
depending on a vendored block's internal contracts. The real blocks are
exercised by the factory's pilot suite.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

from app import dispatch
from app.models import MODELS
from app.validation import sample_for_model


def ok_block(block_id: str, payload: Any = None, action: Any = None, params: Any = None, **kw: Any) -> Dict[str, Any]:
    return {
        "ok": True,
        "status": "ok",
        "block": block_id,
        "action": action,
        "accepted": True,
    }


def stub_blocks(monkeypatch) -> None:
    """Patch every module that bound ``execute`` (handlers bind at import)."""
    monkeypatch.setattr(dispatch, "execute", ok_block, raising=False)
    for name, module in list(sys.modules.items()):
        if name.startswith("app.actions") and hasattr(module, "execute"):
            monkeypatch.setattr(module, "execute", ok_block, raising=False)


def payload(capability_id: str) -> Dict[str, Any]:
    return sample_for_model(MODELS[capability_id])


def auth(token: str = "dev-local-token") -> Dict[str, str]:
    return {"Authorization": "Bearer " + token}
