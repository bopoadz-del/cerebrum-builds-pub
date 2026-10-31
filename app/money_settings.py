"""Money settings for this platform -- read at run time, never typed in.

Country and currency come from the deploy environment (PLATFORM_COUNTRY,
PLATFORM_CURRENCY), else from the locale the customer declared
(docs/declared_locale.json). The tax rate is an operator setting
(PLATFORM_TAX_RATE); with none set, money paths that need it refuse.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[1]


class MoneySettingMissing(RuntimeError):
    """A money path needs a setting nobody declared."""


def _declared() -> dict:
    path = _ROOT / 'docs/declared_locale.json'
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _setting(env: str, key: str) -> Optional[str]:
    value = (os.getenv(env) or "").strip()
    if value:
        return value
    declared = _declared().get(key)
    return str(declared).strip() if declared else None


def country() -> str:
    value = _setting('PLATFORM_COUNTRY', "country")
    if not value:
        raise MoneySettingMissing("no country declared (PLATFORM_COUNTRY)")
    return value


def currency() -> str:
    value = _setting('PLATFORM_CURRENCY', "currency")
    if not value:
        raise MoneySettingMissing("no currency declared (PLATFORM_CURRENCY)")
    return value


def tax_rate() -> float:
    raw = (os.getenv('PLATFORM_TAX_RATE') or "").strip()
    if not raw:
        raise MoneySettingMissing("no tax rate set (PLATFORM_TAX_RATE)")
    return float(raw)


_RATE_NAME = re.compile(r"[a-z][a-z0-9_]*")


def rate(name: str) -> float:
    """A named rate the operator sets (a fee, an fx rate, a discount):
    PLATFORM_RATE_<NAME>. With none set, the money path that needs it
    refuses -- a rate is never a value in code."""
    key = str(name or "").strip().lower()
    if not _RATE_NAME.fullmatch(key):
        raise ValueError(f"a rate name is lower_snake_case, not {name!r}")
    env = 'PLATFORM_RATE_' + key.upper()
    raw = (os.getenv(env) or "").strip()
    if not raw:
        raise MoneySettingMissing(f"no {key} rate set ({env})")
    return float(raw)
