from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import (
    ContextObject,
    ContextObjectVersion,
    Entity,
    OutboxEvent,
    Workspace,
)
from capability_commons.domain.enums import NodeKind
from capability_commons.services.exceptions import NotFoundError


async def get_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError(f"Workspace {workspace_id} not found")
    return workspace


async def get_object(session: AsyncSession, object_id: uuid.UUID) -> ContextObject:
    obj = await session.get(ContextObject, object_id)
    if obj is None:
        raise NotFoundError(f"Object {object_id} not found")
    return obj


async def get_version(session: AsyncSession, version_id: uuid.UUID) -> ContextObjectVersion:
    version = await session.get(ContextObjectVersion, version_id)
    if version is None:
        raise NotFoundError(f"Version {version_id} not found")
    return version


async def get_entity(session: AsyncSession, entity_id: uuid.UUID) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise NotFoundError(f"Entity {entity_id} not found")
    return entity


async def assert_node_exists(session: AsyncSession, node_kind: NodeKind, node_id: uuid.UUID) -> None:
    if node_kind == NodeKind.OBJECT_VERSION:
        await get_version(session, node_id)
        return
    if node_kind == NodeKind.ENTITY:
        await get_entity(session, node_id)
        return
    raise NotFoundError(f"Unsupported node kind: {node_kind}")


async def add_outbox_event(
    session: AsyncSession,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> OutboxEvent:
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event
