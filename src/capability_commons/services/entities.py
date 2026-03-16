from __future__ import annotations

import uuid

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContextObjectEntity, Edge, Entity, EntityAlias
from capability_commons.domain.enums import EntityStatus, EntityType, NodeKind
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

        if source.workspace_id != target.workspace_id:
            raise ConflictError("Cannot merge entities from different workspaces")

        if source.status == EntityStatus.MERGED:
            raise ConflictError(f"Source entity {source_entity_id} is already merged")
        if target.status == EntityStatus.MERGED:
            raise ConflictError(f"Target entity {target_entity_id} has already been merged away")

        # 1. Remap EntityAlias rows from source to target
        # Delete source aliases that already exist on target
        duplicate_aliases = (
            select(EntityAlias.alias)
            .where(EntityAlias.entity_id == target.id)
        ).scalar_subquery()
        await self.session.execute(
            delete(EntityAlias).where(
                and_(
                    EntityAlias.entity_id == source.id,
                    EntityAlias.alias.in_(duplicate_aliases),
                )
            )
        )
        await self.session.execute(
            update(EntityAlias)
            .where(EntityAlias.entity_id == source.id)
            .values(entity_id=target.id)
        )

        # 2. Delete duplicate ContextObjectEntity rows (where both source and target
        #    link to the same version), then remap remaining rows.
        duplicate_versions = (
            select(ContextObjectEntity.context_object_version_id)
            .where(ContextObjectEntity.entity_id == target.id)
        ).scalar_subquery()

        await self.session.execute(
            delete(ContextObjectEntity).where(
                and_(
                    ContextObjectEntity.entity_id == source.id,
                    ContextObjectEntity.context_object_version_id.in_(duplicate_versions),
                )
            )
        )
        await self.session.execute(
            update(ContextObjectEntity)
            .where(ContextObjectEntity.entity_id == source.id)
            .values(entity_id=target.id)
        )

        # 3. Deduplicate + remap Edge rows where source entity appears as src or dst.
        # Delete source-as-src edges that would duplicate a target-as-src edge.
        target_src_edges = (
            select(Edge.dst_id, Edge.dst_node_kind, Edge.edge_type)
            .where(and_(Edge.src_id == target.id, Edge.src_node_kind == NodeKind.ENTITY))
        ).subquery()
        await self.session.execute(
            delete(Edge).where(
                and_(
                    Edge.src_id == source.id,
                    Edge.src_node_kind == NodeKind.ENTITY,
                    Edge.dst_id.in_(select(target_src_edges.c.dst_id)),
                    Edge.dst_node_kind.in_(select(target_src_edges.c.dst_node_kind)),
                    Edge.edge_type.in_(select(target_src_edges.c.edge_type)),
                )
            )
        )
        # Delete source-as-dst edges that would duplicate a target-as-dst edge.
        target_dst_edges = (
            select(Edge.src_id, Edge.src_node_kind, Edge.edge_type)
            .where(and_(Edge.dst_id == target.id, Edge.dst_node_kind == NodeKind.ENTITY))
        ).subquery()
        await self.session.execute(
            delete(Edge).where(
                and_(
                    Edge.dst_id == source.id,
                    Edge.dst_node_kind == NodeKind.ENTITY,
                    Edge.src_id.in_(select(target_dst_edges.c.src_id)),
                    Edge.src_node_kind.in_(select(target_dst_edges.c.src_node_kind)),
                    Edge.edge_type.in_(select(target_dst_edges.c.edge_type)),
                )
            )
        )
        # Remap remaining edges
        await self.session.execute(
            update(Edge)
            .where(and_(Edge.src_id == source.id, Edge.src_node_kind == NodeKind.ENTITY))
            .values(src_id=target.id)
        )
        await self.session.execute(
            update(Edge)
            .where(and_(Edge.dst_id == source.id, Edge.dst_node_kind == NodeKind.ENTITY))
            .values(dst_id=target.id)
        )

        # Delete self-loop edges created by the merge
        await self.session.execute(
            delete(Edge).where(
                Edge.src_id == target.id,
                Edge.dst_id == target.id,
                Edge.src_node_kind == NodeKind.ENTITY,
                Edge.dst_node_kind == NodeKind.ENTITY,
            )
        )

        # 4. Mark source as MERGED
        source.status = EntityStatus.MERGED

        # 5. Emit entity.merged outbox event
        await add_outbox_event(
            self.session,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="entity.merged",
            payload={"source_entity_id": str(source.id), "target_entity_id": str(target.id)},
        )
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(target)
        return target
