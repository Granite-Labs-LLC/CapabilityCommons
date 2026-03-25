"""Tests for evidence API routes."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_evidence_source_requires_auth(client):
    """POST /v1/evidence/sources should require authentication."""
    response = client.post("/v1/evidence/sources", json={
        "source_kind": "BOOK",
        "title": "Test Source",
    })
    assert response.status_code == 401


def test_create_evidence_span_requires_auth(client):
    """POST /v1/evidence/spans should require authentication."""
    response = client.post("/v1/evidence/spans", json={
        "source_id": str(uuid.uuid4()),
        "start_char": 0,
        "end_char": 100,
        "excerpt": "test",
    })
    assert response.status_code == 401


def test_attach_edge_citation_requires_auth(client):
    """POST /v1/evidence/edge_citations should require authentication."""
    response = client.post("/v1/evidence/edge_citations", json={
        "edge_id": str(uuid.uuid4()),
        "evidence_span_id": str(uuid.uuid4()),
    })
    assert response.status_code == 401


def test_list_citations_requires_auth(client):
    """GET citations should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.get(f"/v1/objects/{oid}/versions/{vid}/citations")
    assert response.status_code == 401
