from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from capability_commons.api.deps import DBSession
from capability_commons.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="capability_commons")


@router.get("/health/detailed")
async def health_detailed(session: DBSession) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    overall = "ok" if db_status == "healthy" else "degraded"
    return {
        "status": overall,
        "database": db_status,
        "search": "adapter_ready",
        "graph": "adapter_ready",
    }
