from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import (
    ContextObject,
    ContextObjectEntity,
    ContextObjectFacet,
    ContradictionCase,
    ReviewRecord,
)
from capability_commons.domain.enums import COType, LifecycleState
from capability_commons.graph.adapters.relational_graph import RelationalGraphAdapter
from capability_commons.schemas.public import PublicBundleResponse, PublicObjectResponse
from capability_commons.services.evidence import EvidenceService
from capability_commons.services.exceptions import NotFoundError


class PublicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.evidence = EvidenceService(session)
        self.graph = RelationalGraphAdapter(session)

    async def list_published_objects(self) -> list[PublicObjectResponse]:
        result = await self.session.execute(
            select(ContextObject)
            .where(ContextObject.lifecycle_state == LifecycleState.PUBLISHED)
            .order_by(ContextObject.canonical_title.asc())
        )
        objects = result.scalars().all()
        items = []
        for obj in objects:
            try:
                items.append(await self.render_public_object(obj.slug))
            except Exception:
                continue
        return items

    async def render_public_object(self, slug: str) -> PublicObjectResponse:
        obj = await self._get_published_object(slug)
        version = obj.current_version
        assert version is not None
        facets = await self._group_facets(version.id)
        entities = await self._list_entities(version.id)
        citations = [citation for citation in await self.evidence.list_citations_for_version(version.id)]
        review_summary = await self._review_summary(version.id)
        contradiction_summary = await self._contradiction_summary(version.id)
        members = []
        if obj.type in {COType.MODULE, COType.LEARNING_PATH}:
            members = await self.graph.ordered_members(version.id)
        return PublicObjectResponse(
            slug=obj.slug,
            title=version.title,
            type=obj.type.value,
            summary_short=version.summary_short,
            plain_language=version.plain_language,
            markdown_body=version.markdown_body,
            structured_data=version.structured_data,
            facets=facets,
            entities=entities,
            citations=citations,
            review_summary=review_summary,
            contradiction_summary=contradiction_summary,
            members=members,
        )

    async def render_module_bundle(self, slug: str) -> PublicBundleResponse:
        public_obj = await self.render_public_object(slug)
        bundle = {
            "hook": public_obj.summary_short or public_obj.plain_language[:180],
            "primer": public_obj.plain_language,
            "reference": public_obj.structured_data,
            "teach_forward": public_obj.structured_data.get("teach_forward") or public_obj.structured_data,
        }
        return PublicBundleResponse(object=public_obj, bundle=bundle)

    async def render_learning_path(self, slug: str) -> PublicObjectResponse:
        obj = await self._get_published_object(slug)
        if obj.type != COType.LEARNING_PATH:
            raise NotFoundError(f"Object {slug} is not a learning path")
        return await self.render_public_object(slug)

    async def export_static_bundle(self, slug: str) -> dict:
        public = await self.render_public_object(slug)
        return {"slug": slug, "content": public.model_dump(mode="json")}

    async def _get_published_object(self, slug: str) -> ContextObject:
        result = await self.session.execute(
            select(ContextObject)
            .where(ContextObject.slug == slug, ContextObject.lifecycle_state == LifecycleState.PUBLISHED)
        )
        obj = result.scalar_one_or_none()
        if obj is None or obj.current_version is None:
            raise NotFoundError(f"Published object '{slug}' not found")
        return obj

    async def _group_facets(self, version_id):
        result = await self.session.execute(
            select(ContextObjectFacet).where(ContextObjectFacet.context_object_version_id == version_id)
        )
        grouped = defaultdict(list)
        for row in result.scalars().all():
            grouped[row.facet_type.value].append(row.facet_value)
        return dict(grouped)

    async def _list_entities(self, version_id):
        result = await self.session.execute(
            select(ContextObjectEntity).where(ContextObjectEntity.context_object_version_id == version_id)
        )
        items = []
        for link in result.scalars().all():
            items.append(
                {
                    "entity_id": link.entity.id,
                    "canonical_name": link.entity.canonical_name,
                    "entity_type": link.entity.entity_type.value,
                    "role_label": link.role_label,
                    "mention_count": link.mention_count,
                    "is_primary": link.is_primary,
                }
            )
        return items

    async def _review_summary(self, version_id):
        result = await self.session.execute(
            select(ReviewRecord.outcome, func.count(ReviewRecord.id))
            .where(ReviewRecord.context_object_version_id == version_id)
            .group_by(ReviewRecord.outcome)
        )
        return {outcome.value: count for outcome, count in result.all()}

    async def _contradiction_summary(self, version_id):
        result = await self.session.execute(
            select(ContradictionCase.status, func.count(ContradictionCase.id))
            .where(
                (ContradictionCase.left_version_id == version_id)
                | (ContradictionCase.right_version_id == version_id)
            )
            .group_by(ContradictionCase.status)
        )
        return {status.value: count for status, count in result.all()}
