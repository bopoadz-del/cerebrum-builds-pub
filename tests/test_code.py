"""CODE gate: imports, routes, handlers. pytest -m 'not pilot'."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.schema import REQUIRED_CAPABILITY_IDS, SPECS

pytestmark = pytest.mark.not_pilot

EXPECTED = {
    "booking_management",
    "property_management",
    "dynamic_pricing",
    "review_management",
    "analytics_dashboard",
    "notification_system",
    "search_recommendation",
}


def test_domain_kernel_is_not_a_stub() -> None:
    from app.domain import (
        booking_cascade,
        match_score,
        night_rate,
        notice_priority,
        occupancy_pct,
        property_room_count,
        revpar,
        review_score,
        stay_total,
    )

    assert stay_total("open", "night") == 189.0
    assert stay_total("closed", "week") == 1043.0
    assert booking_cascade("group")["hold_minutes"] == 120
    assert property_room_count("boutique") == 18
    assert night_rate("peak", "open") == 290.0
    assert night_rate("off", "open") == 160.0
    assert review_score("excellent") == 4.8
    assert occupancy_pct("open") == 0.42
    assert revpar("open", "today") == 79.38
    assert notice_priority("confirmation") == "high"
    assert match_score("family") == 0.88


def test_workspace_imports() -> None:
    from app.main import app
    from app.dispatch import BLOCK_DEFAULT_ACTIONS, execute
    from app.store import COLUMNS, list_all, save

    assert app.title == "Hotel Booking Platform"
    assert BLOCK_DEFAULT_ACTIONS["dashboard"] == "render"
    assert BLOCK_DEFAULT_ACTIONS["vector_search"] == "search"
    assert BLOCK_DEFAULT_ACTIONS["formula_executor"] == "execute"
    assert BLOCK_DEFAULT_ACTIONS["capture"] == "extract"
    assert BLOCK_DEFAULT_ACTIONS["storage"] == "store"
    assert BLOCK_DEFAULT_ACTIONS["workflow"] == "run"
    assert BLOCK_DEFAULT_ACTIONS["notification"] == "send"
    assert BLOCK_DEFAULT_ACTIONS["recommendation_template"] == "recommend"
    for capability_id in REQUIRED_CAPABILITY_IDS:
        assert capability_id in COLUMNS
    assert callable(execute)
    assert callable(save)
    assert callable(list_all)


def test_every_capability_has_handler_source() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "actions"
    for capability_id in REQUIRED_CAPABILITY_IDS:
        path = root / f"{capability_id}.py"
        assert path.is_file(), f"missing handler {capability_id}"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert "handle" in names


def test_specs_envelope_vocabulary() -> None:
    for spec in SPECS.values():
        allowed = spec["CONSTRAINTS"]["status"]["allowed_values"]
        assert allowed == ["open", "in_progress", "closed"]
        assert "reference" in spec["FIELDS"]
        assert spec["entity"] == spec["id"]


def test_rag_paths_quoted_in_source() -> None:
    text = (Path(__file__).resolve().parents[1] / "app" / "rag_routes.py").read_text(
        encoding="utf-8"
    )
    assert "/v1/rag/ingest" in text
    assert "/v1/rag/query" in text
    assert "/v1/steward/rag/ingest" in text
    assert "/v1/steward/rag/query" in text


def test_actions_init_has_no_eager_reexport() -> None:
    text = (Path(__file__).resolve().parents[1] / "app" / "actions" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "from app.actions import" not in text


def test_no_airport_or_retail_product_ids() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "airport_readiness",
        "inventory_tracking",
        "Retail Ops Tracker",
        "Airport Operations Platform",
    )
    app_text = (root / "app" / "main.py").read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in app_text
    leftover = [
        p.name
        for p in (root / "app" / "actions").glob("*.py")
        if p.stem.startswith("airport") or p.stem in {"inventory_tracking", "order_management"}
    ]
    assert leftover == []


def test_full_pilot_authorship_floor() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "actions"
    authored = [p for p in root.glob("*.py") if p.name != "__init__.py"]
    assert len(authored) >= 5
    assert len(authored) == len(REQUIRED_CAPABILITY_IDS)
    assert {p.stem for p in authored} == EXPECTED
