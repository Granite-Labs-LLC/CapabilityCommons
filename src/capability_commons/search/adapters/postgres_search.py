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
                    facets=facets_by_version.get(version.id, {}),
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

    async def _vector_search(
        self,
        *,
        workspace_id,
        query_embedding: list[float],
        filters,
        top_k,
        object_types=None,
        only_published=True,
    ) -> list[SearchHit]:
        """Pure vector search via pgvector cosine similarity."""
        vector_score = (
            1 - ContentSegment.embedding.cosine_distance(query_embedding)
        ).label("vector_score")

        stmt = (
            select(
                ContentSegment.context_object_version_id,
                func.max(vector_score).label("score"),
            )
            .join(ContextObjectVersion, ContentSegment.context_object_version_id == ContextObjectVersion.id)
            .join(ContextObject, ContextObjectVersion.context_object_id == ContextObject.id)
            .where(
                ContextObject.workspace_id == workspace_id,
                ContentSegment.embedding.is_not(None),
            )
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

        stmt = stmt.group_by(ContentSegment.context_object_version_id).order_by(
            func.max(vector_score).desc()
        ).limit(top_k)

        result = await self.session.execute(stmt)
        version_score_map = {row[0]: float(row[1]) for row in result.all()}

        if not version_score_map:
            return []

        # Load version/object details for hits
        ver_result = await self.session.execute(
            select(ContextObjectVersion, ContextObject)
            .join(ContextObject, ContextObjectVersion.context_object_id == ContextObject.id)
            .where(ContextObjectVersion.id.in_(version_score_map.keys()))
        )
        facets_by_version = await self._load_facets(list(version_score_map.keys()))

        hits: list[SearchHit] = []
        for version, obj in ver_result.all():
            hits.append(
                SearchHit(
                    object_id=obj.id,
                    version_id=version.id,
                    slug=obj.slug,
                    type=obj.type,
                    title=version.title,
                    summary_short=version.summary_short,
                    plain_language=version.plain_language,
                    score=version_score_map[version.id],
                    lifecycle_state=obj.lifecycle_state,
                    validity_status=version.validity_status.value,
                    facets=facets_by_version.get(version.id, {}),
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    async def search_hybrid(
        self,
        *,
        workspace_id,
        query,
        query_embedding: list[float] | None,
        filters,
        top_k,
        object_types=None,
        only_published=True,
        fts_weight: float = 0.7,
        vector_weight: float = 0.3,
        rrf_k: int = 60,
    ) -> list[SearchHit]:
        """True hybrid search: union FTS + vector candidates via reciprocal rank fusion."""
        if query_embedding is None:
            return await self.search(
                workspace_id=workspace_id,
                query=query,
                filters=filters,
                top_k=top_k,
                object_types=object_types,
                only_published=only_published,
            )

        # Get candidates from both retrieval paths independently
        fts_hits = await self.search(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            top_k=top_k * 3,
            object_types=object_types,
            only_published=only_published,
        )
        vector_hits = await self._vector_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k * 3,
            object_types=object_types,
            only_published=only_published,
        )

        if not fts_hits and not vector_hits:
            return []

        # Build reciprocal rank fusion scores
        # RRF(d) = sum( 1 / (k + rank_i(d)) ) for each ranker i
        fts_rank = {h.version_id: rank for rank, h in enumerate(fts_hits, 1)}
        vec_rank = {h.version_id: rank for rank, h in enumerate(vector_hits, 1)}
        all_version_ids = set(fts_rank.keys()) | set(vec_rank.keys())

        # Collect hit objects by version_id for metadata
        hit_map: dict[uuid.UUID, SearchHit] = {}
        for h in fts_hits:
            hit_map[h.version_id] = h
        for h in vector_hits:
            if h.version_id not in hit_map:
                hit_map[h.version_id] = h

        rrf_scores: list[tuple[uuid.UUID, float]] = []
        for vid in all_version_ids:
            score = 0.0
            if vid in fts_rank:
                score += fts_weight * (1.0 / (rrf_k + fts_rank[vid]))
            if vid in vec_rank:
                score += vector_weight * (1.0 / (rrf_k + vec_rank[vid]))
            rrf_scores.append((vid, score))

        rrf_scores.sort(key=lambda x: x[1], reverse=True)

        result: list[SearchHit] = []
        for vid, score in rrf_scores[:top_k]:
            hit = hit_map[vid]
            hit.score = round(score, 6)
            result.append(hit)
        return result
