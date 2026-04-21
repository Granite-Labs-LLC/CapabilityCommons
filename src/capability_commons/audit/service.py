"""Append-only audit event log for governance transparency."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import AuditEvent
from capability_commons.domain.enums import AuditEventType


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        *,
        event_type: AuditEventType,
        workspace_id: uuid.UUID,
        actor_key_id: uuid.UUID | None = None,
        target_object_id: uuid.UUID | None = None,
        target_version_id: uuid.UUID | None = None,
        target_edge_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_key_id=actor_key_id,
            target_object_id=target_object_id,
            target_version_id=target_version_id,
            target_edge_id=target_edge_id,
            detail=detail,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_object_history(
        self,
        object_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        result = await self.session.execute(
            select(AuditEvent)
            .where(AuditEvent.target_object_id == object_id)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_workspace_timeline(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        event_type: AuditEventType | None = None,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if event_type is not None:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
