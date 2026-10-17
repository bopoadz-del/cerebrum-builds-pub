"""Lazy capability handlers. Do not eager-import handler modules here."""

from __future__ import annotations

import importlib


def load_handler(capability_id: str):
    module = importlib.import_module(f"app.actions.{capability_id}")
    return module.handle
