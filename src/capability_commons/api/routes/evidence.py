from __future__ import annotations

import uuid

from fastapi import APIRouter

from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
from capability_commons.schemas.evidence import (
    CitationResponse,
    CreateEvidenceSourceRequest,
    CreateEvidenceSpanRequest,
    EdgeCitationRequest,
    EvidenceSourceResponse,
    EvidenceSpanResponse,
)
from capability_commons.services.evidence import EvidenceService

router = APIRouter()


@router.post("/evidence/sources", response_model=EvidenceSourceResponse)
async def create_source(request: CreateEvidenceSourceRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> EvidenceSourceResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = EvidenceService(session)
    source = await service.create_source(created_by=actor_id, **data)
    return EvidenceSourceResponse.model_validate(source, from_attributes=True)


@router.post("/evidence/spans", response_model=EvidenceSpanResponse)
async def create_span(request: CreateEvidenceSpanRequest, session: DBSession, workspace: CurrentWorkspace) -> EvidenceSpanResponse:
    service = EvidenceService(session)
    span = await service.create_span(**request.model_dump())
    return EvidenceSpanResponse.model_validate(span, from_attributes=True)


@router.post("/evidence/edge_citations")
async def attach_edge_citation(request: EdgeCitationRequest, session: DBSession, workspace: CurrentWorkspace) -> dict:
    service = EvidenceService(session)
    link = await service.attach_span_to_edge(request.edge_id, request.evidence_span_id)
    return {"edge_id": link.edge_id, "evidence_span_id": link.evidence_span_id}


@router.get("/objects/{object_id}/versions/{version_id}/citations", response_model=list[CitationResponse])
async def list_citations(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession, workspace: CurrentWorkspace) -> list[CitationResponse]:
    service = EvidenceService(session)
    citations = await service.list_citations_for_version(version_id)
    return [CitationResponse.model_validate(item) for item in citations]
