from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import Entity, EntityAlias
from capability_commons.domain.enums import EntityStatus, EntityType
from capability_commons.services.exceptions import ConflictError, NotFoundError
from capability_commons.services.helpers import add_outbox_event, get_entity, get_workspace


class EntityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_entity(
        self,
        workspace_id: uuid.UUID,
        entity_type: EntityType,
        canonical_name: str,
        metadata: dict | None = None,
    ) -> Entity:
        await get_workspace(self.session, workspace_id)
        existing = await self.session.scalar(
            select(Entity).where(
                Entity.workspace_id == workspace_id,
                Entity.entity_type == entity_type,
                Entity.canonical_name == canonical_name,
            )
        )
        if existing is not None:
            raise ConflictError(f"Entity '{canonical_name}' already exists")

        entity = Entity(
            workspace_id=workspace_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            metadata_json=metadata or {},
        )
        self.session.add(entity)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="entity",
            aggregate_id=entity.id,
            event_type="entity.created",
            payload={"workspace_id": str(workspace_id), "entity_id": str(entity.id)},
        )
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def add_alias(self, entity_id: uuid.UUID, alias: str) -> EntityAlias:
        entity = await get_entity(self.session, entity_id)
        existing = await self.session.scalar(
            select(EntityAlias).where(EntityAlias.entity_id == entity_id, EntityAlias.alias == alias)
        )
        if existing is not None:
            return existing
        alias_row = EntityAlias(entity_id=entity.id, alias=alias)
        self.session.add(alias_row)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="entity",
            aggregate_id=entity.id,
            event_type="entity.alias_added",
            payload={"entity_id": str(entity.id), "alias": alias},
        )
        await self.session.commit()
        await self.session.refresh(alias_row)
        return alias_row

    async def resolve_entities(
        self,
        workspace_id: uuid.UUID,
        query: str,
        entity_types: list[EntityType] | None = None,
    ) -> list[Entity]:
        stmt = select(Entity).outerjoin(EntityAlias, EntityAlias.entity_id == Entity.id).where(
            Entity.workspace_id == workspace_id,
            Entity.status == EntityStatus.ACTIVE,
            or_(Entity.canonical_name.ilike(f"%{query}%"), EntityAlias.alias.ilike(f"%{query}%")),
        )
        if entity_types:
            stmt = stmt.where(Entity.entity_type.in_(entity_types))
        result = await self.session.execute(stmt.distinct().order_by(Entity.canonical_name.asc()))
        return list(result.scalars().all())

    async def merge_entities(self, source_entity_id: uuid.UUID, target_entity_id: uuid.UUID) -> Entity:
        if source_entity_id == target_entity_id:
            raise ConflictError("Source and target entity must differ")
        source = await get_entity(self.session, source_entity_id)
        target = await get_entity(self.session, target_entity_id)
        # Explicit TODO: remap all downstream relations in a dedicated migration-safe transaction.
        source.status = EntityStatus.MERGED
        await add_outbox_event(
            self.session,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="entity.merge_requested",
            payload={"source_entity_id": str(source.id), "target_entity_id": str(target.id)},
        )
        await self.session.commit()
        await self.session.refresh(target)
        return target
