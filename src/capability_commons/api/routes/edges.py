from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
from capability_commons.db.models import Edge
from capability_commons.domain.enums import EdgeType
from capability_commons.schemas.edges import CreateEdgeRequest, EdgeResponse
from capability_commons.services.registry import RegistryService

router = APIRouter()


@router.post("/edges", response_model=EdgeResponse)
async def create_edge(request: CreateEdgeRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> EdgeResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = RegistryService(session)
    edge = await service.create_edge(**data, created_by=actor_id)
    return EdgeResponse.model_validate(edge, from_attributes=True)


@router.get("/edges", response_model=list[EdgeResponse])
async def list_edges(
    session: DBSession,
    src_id: uuid.UUID | None = None,
    dst_id: uuid.UUID | None = None,
    edge_type: EdgeType | None = Query(default=None),
) -> list[EdgeResponse]:
    stmt = select(Edge)
    if src_id is not None:
        stmt = stmt.where(Edge.src_id == src_id)
    if dst_id is not None:
        stmt = stmt.where(Edge.dst_id == dst_id)
    if edge_type is not None:
        stmt = stmt.where(Edge.edge_type == edge_type)
    result = await session.execute(stmt.order_by(Edge.created_at.desc()).limit(200))
    return [EdgeResponse.model_validate(edge, from_attributes=True) for edge in result.scalars().all()]
