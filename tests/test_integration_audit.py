"""Integration tests for the audit service against real Postgres."""
from __future__ import annotations

import uuid

import pytest

from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType, COType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.services.registry import RegistryService


@pytest.mark.asyncio
async def test_create_object_emits_audit_event(db_session, workspace):
    """Creating an object should record an object_created audit event."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-audit-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Audit Test Object",
    ))
    await db_session.commit()

    events = await audit.get_object_history(obj.id)
    assert len(events) >= 1
    assert events[0].event_type == AuditEventType.OBJECT_CREATED
    assert events[0].target_object_id == obj.id


@pytest.mark.asyncio
async def test_publish_emits_audit_event(db_session, workspace):
    """Publishing a version should record a version_published audit event."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-audit-pub-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Audit Publish Test",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Audit Publish v1",
        plain_language="Test.",
        markdown_body="# Test",
        structured_data={"definition": "Test."},
    ))
    await svc.publish_version(obj.id, ver.id)
    await db_session.commit()

    events = await audit.get_object_history(obj.id)
    event_types = [e.event_type for e in events]
    assert AuditEventType.OBJECT_CREATED in event_types
    assert AuditEventType.VERSION_CREATED in event_types
    assert AuditEventType.VERSION_PUBLISHED in event_types


@pytest.mark.asyncio
async def test_workspace_timeline(db_session, workspace):
    """get_workspace_timeline should return events across all objects."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    for i in range(3):
        await svc.create_object(CreateObjectRequest(
            workspace_id=workspace.id,
            slug=f"test-audit-tl-{i}-{uuid.uuid4().hex[:6]}",
            type=COType.CONCEPT_NOTE,
            canonical_title=f"Timeline Test {i}",
        ))
    await db_session.commit()

    timeline = await audit.get_workspace_timeline(workspace.id)
    assert len(timeline) >= 3

    creates = await audit.get_workspace_timeline(
        workspace.id, event_type=AuditEventType.OBJECT_CREATED,
    )
    assert all(e.event_type == AuditEventType.OBJECT_CREATED for e in creates)
