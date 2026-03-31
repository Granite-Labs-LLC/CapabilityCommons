from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.services.metrics import MetricsService

router = APIRouter()


@router.get("/metrics/ingest")
async def ingest_metrics(session: DBSession, workspace: CurrentWorkspace) -> dict[str, Any]:
    """Ingest quality metrics (authenticated only)."""
    service = MetricsService(session)
    return await service.ingest_quality()


@router.get("/metrics/answer")
async def answer_metrics(session: DBSession, workspace: CurrentWorkspace) -> dict[str, Any]:
    """Answer quality metrics (authenticated only)."""
    service = MetricsService(session)
    return await service.answer_quality()


@router.get("/metrics/summary")
async def metrics_summary(session: DBSession, workspace: CurrentWorkspace) -> dict[str, Any]:
    """Combined metrics dashboard (authenticated only)."""
    service = MetricsService(session)
    return await service.summary()
