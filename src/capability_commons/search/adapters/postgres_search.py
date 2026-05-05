from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContentSegment, ContextObject, ContextObjectFacet, ContextObjectVersion
from capability_commons.domain.enums import CostBand, FacetType, LifecycleState, RiskBand, StageType
from capability_commons.schemas.search import PublicSearchFilters, SearchHit
from capability_commons.search.adapters.base import SearchAdapter
from capability_commons.search.indexer import VersionIndexer

# Risk bands ordered low → high. "beginner_safe" caps risk at MODERATE.
_RISK_RANK = {
    RiskBand.LOW: 0,
    RiskBand.MODERATE: 1,
    RiskBand.HIGH: 2,
    RiskBand.EXPERT_ONLY: 3,
}
_BEGINNER_SAFE_RISK_CEILING = RiskBand.MODERATE
_COST_RANK = {CostBand.FREE: 0, CostBand.LOW: 1, CostBand.MEDIUM: 2, CostBand.HIGH: 3}


def _attribute_predicates(attrs: PublicSearchFilters | None):
    """Translate UX filters (difficulty/stage/risk_band/beginner_safe/cost_band)
    into SQL predicates on ContextObjectVersion. Returns a list of expressions
    that can be ANDed onto the search query."""
    if attrs is None:
        return []
    preds = []
    if attrs.difficulty_max is not None:
        preds.append(ContextObjectVersion.difficulty <= attrs.difficulty_max)
    if attrs.stage:
        try:
            preds.append(ContextObjectVersion.stage == StageType(attrs.stage))
        except ValueError:
            pass
    if attrs.risk_band:
        try:
            target = RiskBand(attrs.risk_band)
            allowed = [
                rb for rb, rank in _RISK_RANK.items() if rank <= _RISK_RANK[target]
            ]
            preds.append(ContextObjectVersion.risk_band.in_(allowed))
        except ValueError:
            pass
    if attrs.beginner_safe:
        allowed = [
            rb for rb, rank in _RISK_RANK.items()
            if rank <= _RISK_RANK[_BEGINNER_SAFE_RISK_CEILING]
        ]
        preds.append(ContextObjectVersion.risk_band.in_(allowed))
        # Also cap difficulty for "beginner-safe" to ≤3 unless caller already
        # asked for tighter.
        if attrs.difficulty_max is None:
            preds.append(ContextObjectVersion.difficulty <= 3)
    if attrs.cost_band:
        try:
            target = CostBand(attrs.cost_band)
            allowed = [
                cb for cb, rank in _COST_RANK.items() if rank <= _COST_RANK[target]
            ]
            preds.append(ContextObjectVersion.cost_band.in_(allowed))
        except ValueError:
            pass
    return preds


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

    # FTS configuration: english_unaccent runs tokens through `unaccent` before
    # the English stemmer, so "cafe" matches "café" (and vice versa). Defined
    # by alembic 20260504_0001. Falls back at index time too — see migration.
    FTS_CONFIG = "english_unaccent"

    async def search(
        self,
        *,
        workspace_id,
        query,
        filters,
        top_k,
        object_types=None,
        only_published=True,
        attributes: PublicSearchFilters | None = None,
    ) -> list[SearchHit]:
        ts_query = func.websearch_to_tsquery(self.FTS_CONFIG, query)
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

        for predicate in _attribute_predicates(attributes):
            stmt = stmt.where(predicate)

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
        attributes: PublicSearchFilters | None = None,
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

        for predicate in _attribute_predicates(attributes):
            stmt = stmt.where(predicate)

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
        attributes: PublicSearchFilters | None = None,
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
                attributes=attributes,
            )

        # Get candidates from both retrieval paths independently
        fts_hits = await self.search(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            top_k=top_k * 3,
            object_types=object_types,
            only_published=only_published,
            attributes=attributes,
        )
        vector_hits = await self._vector_search(
            workspace_id=workspace_id,
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k * 3,
            object_types=object_types,
            only_published=only_published,
            attributes=attributes,
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
