from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.retrieval.service import RetrievalService
from capability_commons.schemas.retrieval import EvidencePackResponse, RetrievalRequest, RetrievalRunResponse, RetrievalStepResponse

router = APIRouter()


@router.post("/retrieve/evidence_pack")
async def retrieve_evidence_pack(
    request: RetrievalRequest,
    session: DBSession,
    workspace: CurrentWorkspace,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
):
    request.workspace_id = workspace.id
    service = RetrievalService(session)
    pack = await service.execute_plan(request)
    if format == "markdown":
        return PlainTextResponse(pack.rendered_markdown or "")
    return JSONResponse(content=pack.model_dump(mode="json"))


@router.get("/retrieval_runs/{run_id}", response_model=RetrievalRunResponse)
async def get_run(run_id: uuid.UUID, session: DBSession) -> RetrievalRunResponse:
    service = RetrievalService(session)
    return await service.get_run(run_id)


@router.get("/retrieval_runs/{run_id}/steps", response_model=list[RetrievalStepResponse])
async def get_run_steps(run_id: uuid.UUID, session: DBSession) -> list[RetrievalStepResponse]:
    service = RetrievalService(session)
    return await service.get_steps(run_id)
