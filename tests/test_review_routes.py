"""Tests for review API routes."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_submit_review_requires_auth(client):
    """POST /v1/reviews should require authentication."""
    response = client.post("/v1/reviews", json={
        "context_object_version_id": str(uuid.uuid4()),
        "review_type": "TECHNICAL",
        "outcome": "APPROVED",
    })
    assert response.status_code == 401


def test_open_contradiction_requires_auth(client):
    """POST /v1/contradictions should require authentication."""
    response = client.post("/v1/contradictions", json={
        "left_version_id": str(uuid.uuid4()),
        "right_version_id": str(uuid.uuid4()),
        "dimension": "FACTUAL",
        "severity": "MEDIUM",
    })
    assert response.status_code == 401


def test_resolve_contradiction_requires_auth(client):
    """POST /v1/contradictions/{id}/resolve should require authentication."""
    response = client.post(f"/v1/contradictions/{uuid.uuid4()}/resolve", json={
        "resolution_note": "Resolved",
    })
    assert response.status_code == 401


def test_verify_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/verify should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/verify")
    assert response.status_code == 401


def test_dispute_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/dispute should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/dispute")
    assert response.status_code == 401


def test_deprecate_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/deprecate should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/deprecate")
    assert response.status_code == 401
