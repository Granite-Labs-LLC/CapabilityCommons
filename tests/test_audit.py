"""Tests for the audit service."""
from __future__ import annotations


def test_audit_event_type_enum():
    """AuditEventType enum should have all expected members."""
    from capability_commons.domain.enums import AuditEventType

    expected = {
        "object_created", "version_created", "version_published",
        "version_deprecated", "edge_created", "edge_removed",
        "review_submitted", "object_edited",
    }
    actual = {e.value for e in AuditEventType}
    assert actual == expected


def test_audit_event_model_exists():
    """AuditEvent model should exist with expected columns."""
    from capability_commons.db.models import AuditEvent

    columns = {c.name for c in AuditEvent.__table__.columns}
    expected = {
        "id", "workspace_id", "event_type", "actor_key_id",
        "target_object_id", "target_version_id", "target_edge_id",
        "detail", "created_at",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"


def test_audit_service_exists():
    """AuditService should have record_event, get_object_history, get_workspace_timeline."""
    from capability_commons.audit.service import AuditService
    import inspect

    assert hasattr(AuditService, "record_event")
    assert hasattr(AuditService, "get_object_history")
    assert hasattr(AuditService, "get_workspace_timeline")

    sig = inspect.signature(AuditService.record_event)
    params = set(sig.parameters.keys())
    assert "event_type" in params
    assert "workspace_id" in params


def test_audit_schemas():
    """Audit response schema should exist with expected fields."""
    from capability_commons.schemas.audit import AuditEventResponse

    fields = AuditEventResponse.model_fields
    assert "id" in fields
    assert "event_type" in fields
    assert "workspace_id" in fields
    assert "created_at" in fields
    assert "detail" in fields


def test_audit_routes_wired():
    """Audit routes should be wired in the API router."""
    from fastapi.testclient import TestClient
    from capability_commons.main import app

    client = TestClient(app)

    import uuid
    r = client.get(f"/v1/audit/objects/{uuid.uuid4()}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    r = client.get("/v1/audit/timeline")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"


def test_registry_service_imports_audit():
    """RegistryService should import and use AuditService."""
    import inspect
    from capability_commons.services import registry

    source = inspect.getsource(registry)
    assert "AuditService" in source, "RegistryService should reference AuditService"
    assert "record_event" in source, "RegistryService should call record_event"


def test_review_service_imports_audit():
    """ReviewService should import and use AuditService."""
    import inspect
    from capability_commons.services import review

    source = inspect.getsource(review)
    assert "AuditService" in source, "ReviewService should reference AuditService"
