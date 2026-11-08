"""The console manifest, read by app.routes and app.main."""

from __future__ import annotations

from typing import Any, Dict

from app import SCREENS


def screens() -> Dict[str, Dict[str, Any]]:
    return {name: dict(spec) for name, spec in SCREENS.items()}
