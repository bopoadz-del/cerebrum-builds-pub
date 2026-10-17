from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Factory harness may set PYTHONPATH; keep collection working without it.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "pilot: product-gate tests against the booted app")
    config.addinivalue_line("markers", "not_pilot: code-gate imports, routes, and handlers")


OPERATOR_SECRET = "test-operator-" + __import__("secrets").token_hex(16)


@pytest.fixture
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    monkeypatch.setenv("STORAGE_PATH", str(root))
    monkeypatch.delenv("VECTOR_DB_URL", raising=False)
    monkeypatch.setenv("VECTOR_DB_URL", "")
    from app.store import reset_connection

    reset_connection()
    return root


@pytest.fixture
def operator_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("OPERATOR_TOKEN", OPERATOR_SECRET)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    return OPERATOR_SECRET


@pytest.fixture
def client(isolated_storage: Path, operator_secret: str) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {operator_secret}"})
        yield test_client


@pytest.fixture
def anon_client(isolated_storage: Path, operator_secret: str) -> TestClient:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
