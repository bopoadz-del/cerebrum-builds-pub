"""Runtime settings for the Harbourline contracts-administration platform.

Every value the operator owns is read from the environment ONCE, here, and
validated with its own name in the message. Nothing secret has a default: a
missing token fails closed at the request that needs it instead of shipping a
well-known value.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SettingMissing(RuntimeError):
    """A setting the deploy environment must supply was not supplied."""


def require(name: str) -> str:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        raise SettingMissing(f"{name} is not set; the deploy environment must supply it")
    return raw


def option(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def storage_root() -> Path:
    return Path(require("STORAGE_PATH"))


def platform_token() -> str:
    """The platform tenant's token. Read at call time so a rotated secret is
    picked up without a code change, and never defaulted."""
    return require("PLATFORM_TOKEN")


def approved_principals() -> frozenset[str]:
    raw = option("APPROVED_PRINCIPALS")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


PLATFORM_TENANT = option("PLATFORM_TENANT") or "platform"


def int_setting(name: str, default: int, *, minimum: int = 1) -> int:
    raw = option(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingMissing(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise SettingMissing(f"{name} must be >= {minimum}, got {value}")
    return value
