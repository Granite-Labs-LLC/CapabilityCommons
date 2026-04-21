"""Audit event API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType
from capability_commons.schemas.audit import AuditEventResponse

router = APIRouter()


@router.get("/audit/objects/{object_id}", response_model=list[AuditEventResponse])
async def get_object_history(
    object_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AuditEventResponse]:
    svc = AuditService(session)
    events = await svc.get_object_history(object_id, limit=limit, offset=offset)
    return [AuditEventResponse.model_validate(e, from_attributes=True) for e in events]


@router.get("/audit/timeline", response_model=list[AuditEventResponse])
async def get_workspace_timeline(
    session: DBSession,
    workspace: CurrentWorkspace,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: AuditEventType | None = Query(None),
) -> list[AuditEventResponse]:
    svc = AuditService(session)
    events = await svc.get_workspace_timeline(
        workspace.id, limit=limit, offset=offset, event_type=event_type,
    )
    return [AuditEventResponse.model_validate(e, from_attributes=True) for e in events]
