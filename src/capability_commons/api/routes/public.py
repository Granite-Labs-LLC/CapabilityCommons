from __future__ import annotations

from fastapi import APIRouter

from sqlalchemy import func, select

from capability_commons.api.deps import DBSession
from capability_commons.db.models import (
    ContextObject,
    Edge,
    EvidenceSpan,
    IngestJob,
)
from capability_commons.domain.enums import LifecycleState
from capability_commons.publication.service import PublicationService
from capability_commons.schemas.graph import GraphResponse
from capability_commons.schemas.public import PublicBundleResponse, PublicObjectResponse
from capability_commons.schemas.public_metrics import PublicMetricsResponse

router = APIRouter()


@router.get("/public/objects", response_model=list[PublicObjectResponse])
async def list_public_objects(session: DBSession) -> list[PublicObjectResponse]:
    service = PublicationService(session)
    return await service.list_published_objects()


@router.get("/public/graph", response_model=GraphResponse)
async def public_graph(session: DBSession) -> GraphResponse:
    service = PublicationService(session)
    return await service.build_graph_data()


@router.get("/public/objects/{slug}", response_model=PublicObjectResponse)
async def public_object(slug: str, session: DBSession) -> PublicObjectResponse:
    service = PublicationService(session)
    return await service.render_public_object(slug)


@router.get("/public/modules/{slug}", response_model=PublicObjectResponse)
async def public_module(slug: str, session: DBSession) -> PublicObjectResponse:
    service = PublicationService(session)
    return await service.render_public_object(slug)


@router.get("/public/paths/{slug}", response_model=PublicObjectResponse)
async def public_path(slug: str, session: DBSession) -> PublicObjectResponse:
    service = PublicationService(session)
    return await service.render_learning_path(slug)


@router.get("/public/objects/{slug}/bundle", response_model=PublicBundleResponse)
async def public_bundle(slug: str, session: DBSession) -> PublicBundleResponse:
    service = PublicationService(session)
    return await service.render_module_bundle(slug)


@router.get("/public/metrics", response_model=PublicMetricsResponse)
async def public_metrics(session: DBSession) -> PublicMetricsResponse:
    """Public-projected counts for the status page (FE-STATUS-1).

    Anonymous; no auth required. Returns only aggregate counters — no
    per-workspace breakdown, no PII.
    """
    objects = await session.scalar(
        select(func.count(ContextObject.id)).where(
            ContextObject.lifecycle_state == LifecycleState.PUBLISHED
        )
    )
    edges = await session.scalar(select(func.count(Edge.id)))
    evidence_spans = await session.scalar(select(func.count(EvidenceSpan.id)))
    ingest_jobs = await session.scalar(select(func.count(IngestJob.id)))
    last_job_at = await session.scalar(
        select(func.max(IngestJob.completed_at))
    )
    return PublicMetricsResponse(
        objects=int(objects or 0),
        edges=int(edges or 0),
        evidence_spans=int(evidence_spans or 0),
        ingest_jobs=int(ingest_jobs or 0),
        last_ingest_at=last_job_at.isoformat() if last_job_at else None,
    )
