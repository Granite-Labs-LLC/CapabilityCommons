from __future__ import annotations

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.schemas.search import SearchRequest, SearchResponse
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, session: DBSession, workspace: CurrentWorkspace) -> SearchResponse:
    adapter = PostgresSearchAdapter(session)
    hits = await adapter.search(
        workspace_id=workspace.id,
        query=request.query,
        filters=request.facet_filters,
        top_k=request.top_k,
        object_types=request.object_types,
        only_published=request.only_published,
    )
    return SearchResponse(query=request.query, top_k=request.top_k, hits=hits)
