from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContentSegment, ContextObject, ContextObjectFacet, ContextObjectVersion
from capability_commons.domain.enums import FacetType, LifecycleState
from capability_commons.schemas.search import SearchHit
from capability_commons.search.adapters.base import SearchAdapter
from capability_commons.search.indexer import VersionIndexer


class PostgresSearchAdapter(SearchAdapter):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.indexer = VersionIndexer(session)

    async def index_version(self, version_id):
        return await self.indexer.reindex_version(version_id)

    async def delete_version(self, version_id):
        version = await self.session.get(ContextObjectVersion, version_id)
        if version is None:
            return 0
        count = len(version.segments)
        for segment in list(version.segments):
            await self.session.delete(segment)
        await self.session.commit()
        return count

    async def search(
        self,
        *,
        workspace_id,
        query,
        filters,
        top_k,
        object_types=None,
        only_published=True,
    ) -> list[SearchHit]:
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank(ContextObjectVersion.search_tsv, ts_query).label("score")
        stmt: Select = (
            select(ContextObjectVersion, ContextObject, rank)
            .join(ContextObject, ContextObjectVersion.context_object_id == ContextObject.id)
            .where(ContextObject.workspace_id == workspace_id)
            .where(ContextObjectVersion.search_tsv.op("@@")(ts_query))
        )
        if only_published:
            stmt = stmt.where(ContextObject.lifecycle_state == LifecycleState.PUBLISHED)
            stmt = stmt.where(ContextObject.current_version_id == ContextObjectVersion.id)
        if object_types:
            stmt = stmt.where(ContextObject.type.in_(object_types))

        for key, values in filters.items():
            if not values:
                continue
            try:
                facet_type = FacetType(key)
            except ValueError:
                continue
            facet_exists = exists(
                select(ContextObjectFacet.context_object_version_id).where(
                    ContextObjectFacet.context_object_version_id == ContextObjectVersion.id,
                    ContextObjectFacet.facet_type == facet_type,
                    ContextObjectFacet.facet_value.in_(values),
                )
            )
            stmt = stmt.where(facet_exists)

        result = await self.session.execute(stmt.order_by(rank.desc(), ContextObjectVersion.created_at.desc()).limit(top_k))
        rows = result.all()
        version_ids = [row[0].id for row in rows]
        facets_by_version = await self._load_facets(version_ids)

        hits: list[SearchHit] = []
        for version, obj, score in rows:
            hits.append(
                SearchHit(
                    object_id=obj.id,
                    version_id=version.id,
                    slug=obj.slug,
                    type=obj.type,
                    title=version.title,
                    summary_short=version.summary_short,
                    plain_language=version.plain_language,
                    score=float(score or 0.0),
                    lifecycle_state=obj.lifecycle_state,
                    validity_status=version.validity_status.value,
                    matched_facets=facets_by_version.get(version.id, {}),
                )
            )
        return hits

    async def fetch_segments(self, segment_ids):
        if not segment_ids:
            return []
        result = await self.session.execute(
            select(ContentSegment).where(ContentSegment.id.in_(segment_ids)).order_by(ContentSegment.ordinal.asc())
        )
        return list(result.scalars().all())

    async def _load_facets(self, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, list[str]]]:
        if not version_ids:
            return {}
        result = await self.session.execute(
            select(ContextObjectFacet).where(ContextObjectFacet.context_object_version_id.in_(version_ids))
        )
        grouped: dict[uuid.UUID, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for row in result.scalars().all():
            grouped[row.context_object_version_id][row.facet_type.value].append(row.facet_value)
        return {version_id: dict(facets) for version_id, facets in grouped.items()}
