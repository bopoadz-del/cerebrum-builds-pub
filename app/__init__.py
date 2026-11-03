"""Harbourline Civil Works contracts administration platform."""

from __future__ import annotations


def _configure() -> None:
    try:
        from app import kernel_bridge

        kernel_bridge.configure()
    except Exception:  # noqa: BLE001 -- a partial import must not hide the real one
        raise


_configure()
