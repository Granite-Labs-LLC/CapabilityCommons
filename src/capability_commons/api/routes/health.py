from fastapi import APIRouter

from capability_commons.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="capability_commons")


@router.get("/health/detailed")
async def health_detailed() -> dict[str, str]:
    return {"status": "ok", "database": "configured", "search": "adapter_ready", "graph": "adapter_ready"}
