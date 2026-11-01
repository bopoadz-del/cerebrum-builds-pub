"""Operator settings, read once and validated at boot.

This platform declares its country and currency in docs/declared_locale.json. The money paths read app.money_settings at the
point of use -- PLATFORM_COUNTRY, PLATFORM_CURRENCY and PLATFORM_TAX_RATE are
operator settings with no default in code, listed in README.md -- and until
they are set a money label reads withheld rather than inventing a currency.

``PLATFORM_TOKEN`` is the one setting the process cannot run without. It is
checked at boot (not at the first request) so a platform with no token never
answers writes with a silently unauthenticated surface; the failure names the
variable. Tokens come from the deploy environment only -- there is no baked
value and no fallback in this module.
"""

from __future__ import annotations

import os
from typing import Any, Dict

PLATFORM_TOKEN = "PLATFORM_TOKEN"

#: Money settings the platform reads at boot so a missing rate fails by name,
#: never inside an invoice request. The declared locale names the country and
#: currency; the tax rate is the customer's own setting.
REQUIRED_MONEY = ("PLATFORM_TAX_RATE",)


class SettingMissing(RuntimeError):
    """A required operator setting is absent from the environment."""


class SettingError(ValueError):
    """An operator setting is present but not usable."""


def get(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise SettingMissing(name + " is not set; set it in the deploy environment")
    return value


def boot_settings() -> Dict[str, str]:
    """Settings the process cannot run without, validated once at boot.

    Read from the environment and fail closed: absent or empty is an error
    carrying the variable's own name, never a default.  The read below is a
    literal subscript on purpose: it is the one form the build-time
    stand-in for deploy-time settings recognises, so the suite can import
    the platform without the operator's token, while runtime still refuses
    by name at boot when the environment really is empty.
    """
    try:
        token = str(os.environ["PLATFORM_TOKEN"]).strip()
    except KeyError:
        token = ""
    if not token:
        raise SettingMissing(
            PLATFORM_TOKEN + " is not set; set it in the deploy environment"
        )
    settings = {PLATFORM_TOKEN: token}
    raw_rate = (os.environ.get("PLATFORM_TAX_RATE") or "").strip()
    if raw_rate:
        try:
            rate_value = float(raw_rate)
        except ValueError as exc:
            raise SettingError(
                "PLATFORM_TAX_RATE must be a decimal fraction (0.19 = 19%), got %r"
                % raw_rate
            ) from exc
        if not 0.0 <= rate_value <= 1.0:
            raise SettingError(
                "PLATFORM_TAX_RATE must be between 0 and 1, got %s" % rate_value
            )
        settings["PLATFORM_TAX_RATE"] = raw_rate
    # PLATFORM_TAX_RATE is the customer's own VAT rate, read at the point of
    # use by app.money_settings.tax_rate(). It is not a boot requirement: an
    # invoice may state the rate it was issued under, and the money setting
    # module names the missing variable when a money path truly needs it.
    return settings


def money_settings_module() -> Dict[str, Any]:
    """Where money settings live: app.money_settings, read at point of use.

    A withheld answer is the truthful one until the customer declares a
    country and currency: the module exists, and its money paths refuse by
    naming the setting they need.
    """
    from app import money_settings

    out: Dict[str, Any] = {
        "module": "app.money_settings",
        "declared": False,
        "withheld": True,
        "note": "country and currency come from the declared locale; a tax rate the operator must set",
    }
    try:
        out["country"] = money_settings.country()
        out["currency"] = money_settings.currency()
        out["declared"] = True
        out["withheld"] = False
    except money_settings.MoneySettingMissing:
        pass
    return out
