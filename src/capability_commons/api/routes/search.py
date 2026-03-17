from __future__ import annotations

import logging

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.schemas.search import SearchRequest, SearchResponse
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
from capability_commons.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, session: DBSession, workspace: CurrentWorkspace) -> SearchResponse:
    adapter = PostgresSearchAdapter(session)
    embedding_svc = EmbeddingService(session)

    query_embedding = await embedding_svc.embed_query(request.query)

    hits = await adapter.search_hybrid(
        workspace_id=workspace.id,
        query=request.query,
        query_embedding=query_embedding,
        filters=request.facet_filters,
        top_k=request.top_k,
        object_types=request.object_types,
        only_published=request.only_published,
    )
    return SearchResponse(query=request.query, top_k=request.top_k, hits=hits)
