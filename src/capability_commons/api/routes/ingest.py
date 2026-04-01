"""API routes for ingest job management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.domain.enums import IngestJobStatus
from capability_commons.schemas.ingest import (
    CreateIngestJobRequest,
    IngestJobResponse,
)
from capability_commons.services.ingest import IngestService

router = APIRouter()


@router.post("/ingest/jobs", response_model=IngestJobResponse, status_code=201)
async def create_ingest_job(
    request: CreateIngestJobRequest,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> IngestJobResponse:
    """Create a new ingest job for tracking an ingestion pipeline run."""
    service = IngestService(session)
    job = await service.create_job(
        workspace_id=workspace.id,
        project_name=request.project_name,
        source_count=request.source_count,
        config=request.config,
    )
    await session.commit()
    return IngestJobResponse.model_validate(job, from_attributes=True)


@router.get("/ingest/jobs", response_model=list[IngestJobResponse])
async def list_ingest_jobs(
    session: DBSession,
    workspace: CurrentWorkspace,
    status: IngestJobStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IngestJobResponse]:
    """List ingest jobs for the current workspace."""
    service = IngestService(session)
    jobs = await service.list_jobs(workspace.id, status=status, limit=limit, offset=offset)
    return [IngestJobResponse.model_validate(j, from_attributes=True) for j in jobs]


@router.get("/ingest/jobs/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(
    job_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> IngestJobResponse:
    """Get a specific ingest job with all pass statuses."""
    service = IngestService(session)
    job = await service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    if job.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return IngestJobResponse.model_validate(job, from_attributes=True)
