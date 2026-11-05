"""Fixtures for the product's own suite.

The Factory's root conftest owns the ``client`` and the process settings; this
adds only what the product's tests need: the two authenticated principals the
tenancy tests act as.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def auth():
    return {"Authorization": "Bearer " + os.environ.get("PLATFORM_TOKEN", "")}


@pytest.fixture
def auth_b():
    token = os.environ.get("PLATFORM_TOKEN_B", "")
    return {"Authorization": "Bearer " + token}
