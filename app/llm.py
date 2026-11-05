"""No model runs inside this platform, and nothing pretends it does.

The product is deployed offline: its answers come from the contract, the BOQ,
the formula definitions and the governed blocks, and every answer carries the
authority label of the layer it came from. This module is the honest seam for
a deployment that wants a model in front of it: the call site exists and
refuses loudly instead of returning a generated sentence nobody can ground.
"""

from __future__ import annotations

import os
from typing import Any, Dict


class LlmUnavailable(RuntimeError):
    """A model was asked for and the platform has none configured."""


def enabled() -> bool:
    return bool((os.environ.get("PLATFORM_LLM_ENDPOINT") or "").strip())


def complete(prompt: str, **_kwargs: Any) -> Dict[str, Any]:
    """Refuse: this platform answers from its documents, not from a model.

    A deployment that sets PLATFORM_LLM_ENDPOINT still gets this refusal until
    an egress-audited client is wired; nothing is silently invented.
    """
    del prompt
    raise LlmUnavailable(
        "this platform is deployed offline and answers from the contract, the "
        "BOQ and its formulas; no language model is configured"
    )
