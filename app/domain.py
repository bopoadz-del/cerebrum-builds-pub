"""Hotel booking kernel. Envelope-driven; no invented caller contracts."""

from __future__ import annotations

from typing import Any, Dict, Tuple

STATUS_VALUES = ("open", "in_progress", "closed")
STATUS_NEXT: Dict[str, Tuple[str, ...]] = {
    "open": ("in_progress",),
    "in_progress": ("closed",),
    "closed": (),
}

STAY_NIGHTS = {"night": 1, "week": 7, "group": 3}
NIGHTLY_RATE = {"open": 189.0, "in_progress": 165.0, "closed": 149.0}
BOOKING_QUEUE = {
    "night": {"next_action": "confirm_room", "hold_minutes": 30, "queue": "front_desk"},
    "week": {"next_action": "extend_hold", "hold_minutes": 90, "queue": "reservations"},
    "group": {"next_action": "assign_block", "hold_minutes": 120, "queue": "groups"},
}

PROPERTY_ROOMS = {"hotel": 48, "resort": 120, "boutique": 18}
PROPERTY_BAND = {"hotel": "urban", "resort": "destination", "boutique": "lifestyle"}

SEASON_FACTOR = {"peak": 1.45, "shoulder": 1.10, "off": 0.80}
STATUS_RATE_ADJ = {"open": 1.0, "in_progress": 0.95, "closed": 0.90}
BASE_RATE = 200.0

RATING_SCORE = {"excellent": 4.8, "good": 3.6, "poor": 1.9}
REVIEW_PUBLISH = {"open": "pending_moderation", "in_progress": "published", "closed": "archived"}

OCCUPANCY = {"open": 0.42, "in_progress": 0.71, "closed": 0.88}
ADR = {"today": 189.0, "week": 205.0, "month": 176.0}
HORIZON_BAND = {"today": "tactical", "week": "planning", "month": "strategic"}

NOTICE_PRIORITY = {"confirmation": "high", "reminder": "normal", "update": "normal"}
INTENT_MATCH = {"leisure": 0.82, "business": 0.74, "family": 0.88}


def envelope_status(payload: Dict[str, Any]) -> str:
    status = str(payload.get("status") or "open")
    return status if status in STATUS_VALUES else "open"


def allowed_next_status(status: str) -> Tuple[str, ...]:
    return STATUS_NEXT.get(status, ())


def stay_nights(stay_kind: str) -> int:
    return STAY_NIGHTS.get(stay_kind, STAY_NIGHTS["night"])


def nightly_rate(status: str) -> float:
    return NIGHTLY_RATE.get(status, NIGHTLY_RATE["open"])


def stay_total(status: str, stay_kind: str) -> float:
    return round(nightly_rate(status) * stay_nights(stay_kind), 2)


def booking_cascade(stay_kind: str) -> Dict[str, Any]:
    return dict(BOOKING_QUEUE.get(stay_kind, BOOKING_QUEUE["night"]))


def property_room_count(property_kind: str) -> int:
    return PROPERTY_ROOMS.get(property_kind, PROPERTY_ROOMS["hotel"])


def property_band(property_kind: str) -> str:
    return PROPERTY_BAND.get(property_kind, PROPERTY_BAND["hotel"])


def night_rate(season: str, status: str) -> float:
    factor = SEASON_FACTOR.get(season, SEASON_FACTOR["peak"])
    adj = STATUS_RATE_ADJ.get(status, STATUS_RATE_ADJ["open"])
    return round(BASE_RATE * factor * adj, 2)


def review_score(rating_band: str) -> float:
    return RATING_SCORE.get(rating_band, RATING_SCORE["excellent"])


def review_publish_state(status: str) -> str:
    return REVIEW_PUBLISH.get(status, REVIEW_PUBLISH["open"])


def occupancy_pct(status: str) -> float:
    return OCCUPANCY.get(status, OCCUPANCY["open"])


def adr_for(horizon: str) -> float:
    return ADR.get(horizon, ADR["today"])


def revpar(status: str, horizon: str) -> float:
    return round(occupancy_pct(status) * adr_for(horizon), 2)


def dashboard_band(horizon: str) -> str:
    return HORIZON_BAND.get(horizon, HORIZON_BAND["today"])


def notice_priority(notice_kind: str) -> str:
    return NOTICE_PRIORITY.get(notice_kind, "normal")


def match_score(stay_intent: str) -> float:
    return INTENT_MATCH.get(stay_intent, INTENT_MATCH["leisure"])
