"""Contract terms named by the source documents, overridable by the operator.

The rates below are the uploaded contract excerpt's own figures (Clauses 8.2,
8.7, 11.1, 14.3, 4.2).  They are settings, not code constants: the operator can
change a renegotiated rate without a code change.  Currency comes from
``app.money_settings``, never from a literal here.

    document:a2e79e3d662b42f1b56d5faafd651ffe_harbourline_contract.pdf
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Dict

#: The uploaded contract excerpt this platform administers. A clause record
#: that cites no other evidence is cited to its source of record.
SOURCE_OF_RECORD = "document:a2e79e3d662b42f1b56d5faafd651ffe_harbourline_contract.pdf"

DEFAULTS: Dict[str, str] = {
    "TIME_FOR_COMPLETION_DAYS": "730",
    "DELAY_DAMAGES_DAILY_RATE": "0.001",
    "DELAY_DAMAGES_CAP_RATIO": "0.10",
    "DEFECTS_NOTIFICATION_DAYS": "365",
    "RETENTION_RATE": "0.05",
    "RETENTION_RELEASE_AT_TAKING_OVER": "0.50",
    "PERFORMANCE_SECURITY_RATE": "0.10",
}


def setting(name: str) -> float:
    raw = (os.environ.get(name) or "").strip() or DEFAULTS[str(name)]
    return float(raw)


def time_for_completion_days() -> int:
    return int(setting("TIME_FOR_COMPLETION_DAYS"))


def delay_damages_daily_rate() -> float:
    return setting("DELAY_DAMAGES_DAILY_RATE")


def delay_damages_cap_ratio() -> float:
    return setting("DELAY_DAMAGES_CAP_RATIO")


def defects_notification_days() -> int:
    return int(setting("DEFECTS_NOTIFICATION_DAYS"))


def retention_rate() -> float:
    return setting("RETENTION_RATE")


def retention_release_at_taking_over() -> float:
    return setting("RETENTION_RELEASE_AT_TAKING_OVER")


def performance_security_rate() -> float:
    return setting("PERFORMANCE_SECURITY_RATE")


def completion_date(commencement: str) -> str:
    """Commencement + Time for Completion (Clause 8.2).

    A commencement that is not an ISO date is refused here: the platform must
    not invent a commencement the contract never stated.
    """
    start = date.fromisoformat(str(commencement))
    return (start + timedelta(days=time_for_completion_days())).isoformat()


def taking_over_date(commencement: str, actual_completion: str = "") -> str:
    """The date the Defects Notification Period (Clause 11.1) runs from."""
    base = actual_completion or commencement
    return date.fromisoformat(str(base)).isoformat()


def currency() -> str:
    from app.money_settings import currency as declared_currency

    return declared_currency()


def cited_terms() -> Dict[str, object]:
    """The terms as this deployment currently sets them, with clause refs."""
    rows = [
        {"clause": "8.2", "name": "Time for Completion (days)", "value": time_for_completion_days()},
        {"clause": "8.7", "name": "Delay damages daily rate", "value": delay_damages_daily_rate()},
        {"clause": "8.7", "name": "Delay damages cap ratio", "value": delay_damages_cap_ratio()},
        {"clause": "11.1", "name": "Defects Notification Period (days)", "value": defects_notification_days()},
        {"clause": "14.3", "name": "Retention rate", "value": retention_rate()},
        {"clause": "14.3", "name": "Retention released at Taking-Over", "value": retention_release_at_taking_over()},
        {"clause": "4.2", "name": "Performance Security rate", "value": performance_security_rate()},
    ]
    return {
        "source": SOURCE_OF_RECORD,
        "terms": rows,
    }
