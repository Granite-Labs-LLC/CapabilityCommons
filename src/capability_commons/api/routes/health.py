from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from capability_commons.api.deps import DBSession
from capability_commons.config import get_settings
from capability_commons.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="capability_commons")


@router.get("/health/detailed")
async def health_detailed(session: DBSession) -> dict:
    settings = get_settings()
    checks: dict[str, str] = {}

    # Database connectivity
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Migration version
    try:
        result = await session.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")
        )
        versions = [row[0] for row in result.fetchall()]
        checks["migration_heads"] = ",".join(versions) if versions else "none"
    except Exception:
        checks["migration_heads"] = "unknown"

    # Embedding service availability
    checks["embedding_configured"] = "yes" if settings.openai_api_key else "no"

    overall = "ok" if checks["database"] == "healthy" else "degraded"
    return {"status": overall, **checks}
