from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import (
    ContextObject,
    ContextObjectEntity,
    ContextObjectFacet,
    ContextObjectVersion,
    Edge,
)
from capability_commons.audit.service import AuditService
from capability_commons.services.publish_gate import PublishGate
from capability_commons.domain.enums import (
    AuditEventType,
    COType,
    EdgeType,
    LifecycleState,
    NodeKind,
    ProvenanceMethod,
    RelationStatus,
    ValidityStatus,
    VisibilityType,
    FacetType,
)
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest, UpdateVersionRequest
from capability_commons.schemas.structured_data import validate_structured_data_or_raise
from capability_commons.services.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from capability_commons.services.helpers import add_outbox_event, assert_node_exists, get_entity, get_object, get_version, get_workspace


class RegistryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_object(self, request: CreateObjectRequest, actor_id: uuid.UUID | None = None) -> ContextObject:
        await get_workspace(self.session, request.workspace_id)
        existing = await self.session.scalar(
            select(ContextObject).where(
                ContextObject.workspace_id == request.workspace_id,
                ContextObject.slug == request.slug,
            )
        )
        if existing is not None:
            raise ConflictError(f"Object slug '{request.slug}' already exists in workspace")

        obj = ContextObject(
            workspace_id=request.workspace_id,
            slug=request.slug,
            type=request.type,
            canonical_title=request.canonical_title,
            visibility=request.visibility,
            default_language=request.default_language,
            created_by=actor_id,
        )
        self.session.add(obj)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="context_object",
            aggregate_id=obj.id,
            event_type="object.created",
            payload={
                "workspace_id": str(obj.workspace_id),
                "object_id": str(obj.id),
                "type": obj.type.value,
                "slug": obj.slug,
            },
        )
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.OBJECT_CREATED,
            workspace_id=obj.workspace_id,
            actor_key_id=actor_id,
            target_object_id=obj.id,
            detail={"slug": obj.slug, "type": obj.type.value},
        )
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def create_version(
        self,
        object_id: uuid.UUID,
        request: CreateVersionRequest,
        actor_id: uuid.UUID | None = None,
    ) -> ContextObjectVersion:
        obj = await get_object(self.session, object_id)
        structured_data = validate_structured_data_or_raise(obj.type, request.structured_data)
        next_version_no = (
            await self.session.scalar(
                select(func.coalesce(func.max(ContextObjectVersion.version_no), 0) + 1).where(
                    ContextObjectVersion.context_object_id == object_id
                )
            )
            or 1
        )
        version = ContextObjectVersion(
            context_object_id=object_id,
            version_no=int(next_version_no),
            title=request.title,
            summary_short=request.summary_short,
            summary_medium=request.summary_medium,
            summary_long=request.summary_long,
            plain_language=request.plain_language,
            markdown_body=request.markdown_body,
            structured_data=structured_data,
            validity_status=request.validity_status,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            stage=request.stage,
            difficulty=request.difficulty,
            estimated_minutes=request.estimated_minutes,
            cost_band=request.cost_band,
            risk_band=request.risk_band,
            reading_level=request.reading_level,
            beginner_safe=request.beginner_safe,
            teach_forward_ready=request.teach_forward_ready,
            requires_professional=request.requires_professional,
            source_confidence=request.source_confidence,
            evidence_confidence=request.evidence_confidence,
            locale_scope=request.locale_scope,
            language_code=request.language_code,
            supersedes_version_id=request.supersedes_version_id,
            checksum=request.checksum,
            created_by=actor_id,
        )
        self.session.add(version)
        obj.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="context_object_version",
            aggregate_id=version.id,
            event_type="version.created",
            payload={
                "object_id": str(obj.id),
                "version_id": str(version.id),
                "version_no": version.version_no,
            },
        )
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.VERSION_CREATED,
            workspace_id=obj.workspace_id,
            actor_key_id=actor_id,
            target_object_id=obj.id,
            target_version_id=version.id,
            detail={"version_no": version.version_no},
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def update_draft_version(
        self,
        object_id: uuid.UUID,
        version_id: uuid.UUID,
        request: UpdateVersionRequest,
    ) -> ContextObjectVersion:
        obj = await get_object(self.session, object_id)
        version = await get_version(self.session, version_id)
        if version.context_object_id != obj.id:
            raise ConflictError("Version does not belong to object")
        if obj.current_version_id == version.id:
            raise ForbiddenError("Published current versions are immutable; create a new version instead")

        patch = request.model_dump(exclude_unset=True)
        if "structured_data" in patch:
            patch["structured_data"] = validate_structured_data_or_raise(obj.type, patch["structured_data"])
        for key, value in patch.items():
            setattr(version, key, value)
        obj.updated_at = datetime.now(timezone.utc)
        await add_outbox_event(
            self.session,
            aggregate_type="context_object_version",
            aggregate_id=version.id,
            event_type="version.updated",
            payload={"object_id": str(obj.id), "version_id": str(version.id)},
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def attach_facets(
        self,
        object_id: uuid.UUID,
        version_id: uuid.UUID,
        facets: list[dict[str, str]],
    ) -> ContextObjectVersion:
        version = await self._assert_version_belongs(object_id, version_id)
        for facet in facets:
            facet_row = ContextObjectFacet(
                context_object_version_id=version.id,
                facet_type=FacetType(facet["facet_type"]),
                facet_value=facet["facet_value"],
            )
            await self.session.merge(facet_row)
        await add_outbox_event(
            self.session,
            aggregate_type="context_object_version",
            aggregate_id=version.id,
            event_type="version.facets_attached",
            payload={"version_id": str(version.id), "facet_count": len(facets)},
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def attach_entities(
        self,
        object_id: uuid.UUID,
        version_id: uuid.UUID,
        entities: list[dict[str, Any]],
    ) -> ContextObjectVersion:
        version = await self._assert_version_belongs(object_id, version_id)
        for entry in entities:
            await get_entity(self.session, entry["entity_id"])
            link = ContextObjectEntity(
                context_object_version_id=version.id,
                entity_id=entry["entity_id"],
                mention_count=entry.get("mention_count", 1),
                role_label=entry.get("role_label"),
                is_primary=entry.get("is_primary", False),
            )
            await self.session.merge(link)
        await add_outbox_event(
            self.session,
            aggregate_type="context_object_version",
            aggregate_id=version.id,
            event_type="version.entities_attached",
            payload={"version_id": str(version.id), "entity_count": len(entities)},
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def create_edge(
        self,
        *,
        workspace_id: uuid.UUID,
        src_node_kind: NodeKind,
        src_id: uuid.UUID,
        edge_type: EdgeType,
        dst_node_kind: NodeKind,
        dst_id: uuid.UUID,
        ordinal: int | None = None,
        confidence: Decimal | float = Decimal("1.0"),
        provenance_method: ProvenanceMethod = ProvenanceMethod.HUMAN_AUTHORED,
        status: RelationStatus = RelationStatus.CURRENT,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> Edge:
        await get_workspace(self.session, workspace_id)
        await assert_node_exists(self.session, src_node_kind, src_id)
        await assert_node_exists(self.session, dst_node_kind, dst_id)
        await self._validate_edge_invariants(
            edge_type=edge_type,
            src_node_kind=src_node_kind,
            src_id=src_id,
            dst_node_kind=dst_node_kind,
            dst_id=dst_id,
        )
        edge = Edge(
            workspace_id=workspace_id,
            src_node_kind=src_node_kind,
            src_id=src_id,
            edge_type=edge_type,
            dst_node_kind=dst_node_kind,
            dst_id=dst_id,
            ordinal=ordinal,
            confidence=confidence,
            provenance_method=provenance_method,
            status=status,
            valid_from=valid_from,
            valid_to=valid_to,
            metadata_json=metadata or {},
            created_by=created_by,
        )
        self.session.add(edge)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="edge",
            aggregate_id=edge.id,
            event_type="edge.created",
            payload={"edge_id": str(edge.id), "edge_type": edge.edge_type.value},
        )
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.EDGE_CREATED,
            workspace_id=workspace_id,
            actor_key_id=created_by,
            target_edge_id=edge.id,
            detail={"edge_type": edge.edge_type.value, "src_id": str(src_id), "dst_id": str(dst_id)},
        )
        await self.session.commit()
        await self.session.refresh(edge)
        return edge

    async def publish_version(self, object_id: uuid.UUID, version_id: uuid.UUID, bypass_gate: bool = False) -> ContextObject:
        obj = await get_object(self.session, object_id)
        version = await self._assert_version_belongs(object_id, version_id)
        validate_structured_data_or_raise(obj.type, version.structured_data)

        # Publish gate — block if safety checks fail
        if not bypass_gate:
            gate = PublishGate(self.session)
            result = await gate.check(version, obj.type)
            if not result.passed:
                raise ValueError(
                    f"Publish gate blocked: {'; '.join(result.blockers)}"
                )

        now = datetime.now(timezone.utc)

        if obj.current_version_id and obj.current_version_id != version.id:
            prior_version = await get_version(self.session, obj.current_version_id)
            prior_version.validity_status = ValidityStatus.SUPERSEDED

        version.validity_status = ValidityStatus.CURRENT
        obj.current_version_id = version.id
        obj.canonical_title = version.title
        obj.lifecycle_state = LifecycleState.PUBLISHED
        obj.published_at = now
        obj.updated_at = now
        await add_outbox_event(
            self.session,
            aggregate_type="context_object",
            aggregate_id=obj.id,
            event_type="version.published",
            payload={"object_id": str(obj.id), "version_id": str(version.id)},
        )
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.VERSION_PUBLISHED,
            workspace_id=obj.workspace_id,
            target_object_id=obj.id,
            target_version_id=version.id,
        )
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def deprecate_object(self, object_id: uuid.UUID, reason: str | None = None) -> ContextObject:
        obj = await get_object(self.session, object_id)
        obj.lifecycle_state = LifecycleState.DEPRECATED
        obj.updated_at = datetime.now(timezone.utc)
        await add_outbox_event(
            self.session,
            aggregate_type="context_object",
            aggregate_id=obj.id,
            event_type="object.deprecated",
            payload={"object_id": str(obj.id), "reason": reason},
        )
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def supersede_with_version(self, object_id: uuid.UUID, version_id: uuid.UUID) -> ContextObject:
        return await self.publish_version(object_id, version_id)

    async def get_object(self, object_id: uuid.UUID) -> ContextObject:
        return await get_object(self.session, object_id)

    async def get_version(self, version_id: uuid.UUID) -> ContextObjectVersion:
        return await get_version(self.session, version_id)

    async def list_versions(self, object_id: uuid.UUID) -> list[ContextObjectVersion]:
        await get_object(self.session, object_id)
        result = await self.session.execute(
            select(ContextObjectVersion)
            .where(ContextObjectVersion.context_object_id == object_id)
            .order_by(ContextObjectVersion.version_no.desc())
        )
        return list(result.scalars().all())

    async def get_current(self, object_id: uuid.UUID) -> ContextObjectVersion:
        obj = await get_object(self.session, object_id)
        if obj.current_version_id is None:
            raise NotFoundError("Object does not have a current published version")
        return await get_version(self.session, obj.current_version_id)

    async def list_current(
        self,
        workspace_id: uuid.UUID,
        *,
        object_types: list[COType] | None = None,
        visibility: VisibilityType | None = VisibilityType.PUBLIC,
    ) -> list[ContextObject]:
        stmt = select(ContextObject).where(ContextObject.workspace_id == workspace_id, ContextObject.current_version_id.is_not(None))
        if object_types:
            stmt = stmt.where(ContextObject.type.in_(object_types))
        if visibility is not None:
            stmt = stmt.where(ContextObject.visibility == visibility)
        result = await self.session.execute(stmt.order_by(ContextObject.slug.asc()))
        return list(result.scalars().all())

    async def mark_version_validity(
        self,
        object_id: uuid.UUID,
        version_id: uuid.UUID,
        validity_status: ValidityStatus,
    ) -> ContextObjectVersion:
        version = await self._assert_version_belongs(object_id, version_id)
        version.validity_status = validity_status
        if validity_status in {ValidityStatus.DEPRECATED, ValidityStatus.RETRACTED}:
            obj = await get_object(self.session, object_id)
            if obj.current_version_id == version.id:
                obj.lifecycle_state = LifecycleState.DEPRECATED
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def list_objects(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int = 20,
    ) -> tuple[list[ContextObject], int]:
        count_stmt = select(func.count(ContextObject.id)).where(
            ContextObject.workspace_id == workspace_id
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(ContextObject)
            .where(ContextObject.workspace_id == workspace_id)
            .order_by(ContextObject.created_at.desc(), ContextObject.id.desc())
            .limit(limit + 1)
        )
        if cursor_id is not None:
            cursor_obj = await self.session.get(ContextObject, cursor_id)
            if cursor_obj is not None:
                stmt = stmt.where(
                    (ContextObject.created_at < cursor_obj.created_at)
                    | (
                        (ContextObject.created_at == cursor_obj.created_at)
                        & (ContextObject.id < cursor_id)
                    )
                )

        result = await self.session.execute(stmt)
        objects = list(result.scalars().all())
        return objects, total

    async def _assert_version_belongs(self, object_id: uuid.UUID, version_id: uuid.UUID) -> ContextObjectVersion:
        version = await get_version(self.session, version_id)
        if version.context_object_id != object_id:
            raise ConflictError("Version does not belong to object")
        return version

    async def _validate_edge_invariants(
        self,
        *,
        edge_type: EdgeType,
        src_node_kind: NodeKind,
        src_id: uuid.UUID,
        dst_node_kind: NodeKind,
        dst_id: uuid.UUID,
    ) -> None:
        if edge_type == EdgeType.CONTAINS and src_node_kind != NodeKind.OBJECT_VERSION:
            raise ValidationError("contains edges must originate from object versions")

        if edge_type in {
            EdgeType.REQUIRES_TOOL,
            EdgeType.REQUIRES_MATERIAL,
            EdgeType.APPLIES_IN,
            EdgeType.ADAPTED_FOR,
        } and dst_node_kind != NodeKind.ENTITY:
            raise ValidationError(f"{edge_type.value} edges normally target entities")

        if edge_type in {EdgeType.SUPERSEDES, EdgeType.DEPRECATED_BY, EdgeType.CORRECTED_BY}:
            if src_node_kind != NodeKind.OBJECT_VERSION or dst_node_kind != NodeKind.OBJECT_VERSION:
                raise ValidationError(f"{edge_type.value} edges must link object_version -> object_version")

        if edge_type == EdgeType.ASSESSED_BY:
            if src_node_kind != NodeKind.OBJECT_VERSION or dst_node_kind != NodeKind.OBJECT_VERSION:
                raise ValidationError("assessed_by must link object_version -> object_version")
            target = await get_version(self.session, dst_id)
            if target.context_object.type != COType.ASSESSMENT:
                raise ValidationError("assessed_by target must be an assessment")

        if edge_type == EdgeType.TRANSLATED_FROM:
            if src_node_kind != NodeKind.OBJECT_VERSION or dst_node_kind != NodeKind.OBJECT_VERSION:
                raise ValidationError("translated_from must link object_version -> object_version")
            src_version = await get_version(self.session, src_id)
            dst_version = await get_version(self.session, dst_id)
            if src_version.context_object.type != dst_version.context_object.type:
                raise ValidationError("translated_from must connect objects of equivalent semantic type")

