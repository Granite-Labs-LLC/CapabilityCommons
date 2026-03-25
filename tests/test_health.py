"""Tests for health endpoint."""
from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from capability_commons.api.routes import health
from capability_commons.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_detailed_health_accepts_session():
    """Detailed health check must accept a DB session to verify connectivity."""
    sig = inspect.signature(health.health_detailed)
    assert "session" in sig.parameters


def test_check_migrations_function_exists():
    """Migration check function should be importable."""
    from capability_commons.main import check_pending_migrations
    assert callable(check_pending_migrations)


def test_swagger_ui_accessible():
    """Swagger UI should be accessible at /docs."""
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc_accessible():
    """ReDoc should be accessible at /redoc."""
    client = TestClient(app)
    response = client.get("/redoc")
    assert response.status_code == 200
