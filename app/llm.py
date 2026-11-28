"""Offline LLM surface.

The platform runs without network access.  This module exposes the provider
contract and fails closed with a typed refusal when no local provider is
wired; it never fabricates an answer.
"""

from __future__ import annotations

import os
from typing import Any, Dict


class LLMUnavailable(RuntimeError):
    pass


def provider_name() -> str:
    return (os.getenv("PLATFORM_LLM_PROVIDER") or "").strip()


def generate(prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    provider = provider_name()
    if not provider:
        raise LLMUnavailable("no local LLM provider configured (PLATFORM_LLM_PROVIDER)")
    raise LLMUnavailable("provider %r is not wired for offline execution" % provider)


def health() -> Dict[str, Any]:
    provider = provider_name()
    return {"ok": bool(provider), "provider": provider or None, "mode": "offline"}
