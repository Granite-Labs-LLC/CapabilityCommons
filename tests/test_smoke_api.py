"""Smoke tests: verify route wiring. Auth-required routes return 401 without a key.

These tests only check that routes are registered and auth dependencies fire before
any DB access, so they run in the unit-test CI job without a live Postgres. Happy-path
behavior for public endpoints is covered by tests/test_integration_publication.py.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_objects_requires_auth(client):
    r = client.get("/v1/objects")
    assert r.status_code == 401


def test_create_edge_requires_auth(client):
    r = client.post("/v1/edges", json={
        "src_node_kind": "object_version",
        "src_id": str(uuid.uuid4()),
        "edge_type": "prerequisite_for",
        "dst_node_kind": "object_version",
        "dst_id": str(uuid.uuid4()),
    })
    assert r.status_code == 401


def test_create_object_requires_auth(client):
    r = client.post("/v1/objects", json={
        "workspace_id": str(uuid.uuid4()),
        "slug": "test",
        "type": "concept_note",
        "canonical_title": "Test",
    })
    assert r.status_code == 401


def test_evidence_requires_auth(client):
    r = client.post("/v1/evidence/sources", json={
        "source_kind": "book",
        "title": "Test Source",
    })
    assert r.status_code == 401


def test_reviews_requires_auth(client):
    r = client.post("/v1/reviews", json={
        "context_object_version_id": str(uuid.uuid4()),
        "review_type": "safety",
        "outcome": "approved",
    })
    assert r.status_code == 401


def test_retrieval_requires_auth(client):
    r = client.post("/v1/retrieve/evidence_pack", json={
        "query": "test",
        "intent": "how_to",
    })
    assert r.status_code == 401


def test_ingest_requires_auth(client):
    r = client.post("/v1/ingest/jobs", json={
        "source_id": "src.test.book.2024",
        "source_title": "Test Book",
    })
    assert r.status_code == 401


def test_review_queue_requires_auth(client):
    r = client.get("/v1/reviews/queue")
    assert r.status_code == 401


def test_audit_object_history_requires_auth(client):
    r = client.get(f"/v1/audit/objects/{uuid.uuid4()}")
    assert r.status_code == 401


def test_audit_timeline_requires_auth(client):
    r = client.get("/v1/audit/timeline")
    assert r.status_code == 401


def test_file_upload_requires_auth(client):
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    r = client.post(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401


def test_file_list_requires_auth(client):
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    r = client.get(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401


def test_contradictions_requires_auth(client):
    r = client.post("/v1/contradictions", json={
        "left_version_id": str(uuid.uuid4()),
        "right_version_id": str(uuid.uuid4()),
        "dimension": "method",
        "severity": "medium",
    })
    assert r.status_code == 401


def test_verify_requires_auth(client):
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    r = client.post(f"/v1/objects/{oid}/versions/{vid}/verify")
    assert r.status_code == 401


def test_deprecate_requires_auth(client):
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    r = client.post(f"/v1/objects/{oid}/versions/{vid}/deprecate")
    assert r.status_code == 401
