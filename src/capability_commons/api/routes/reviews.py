from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.db.models import ContextObject, ContextObjectVersion
from capability_commons.domain.enums import LifecycleState, RiskBand
from capability_commons.schemas.reviews import (
    ContradictionResponse,
    CreateReviewRequest,
    ReviewResponse,
    ResolveContradictionRequest,
    VersionValidityActionResponse,
)
from capability_commons.schemas.reviews import OpenContradictionRequest
from capability_commons.services.registry import RegistryService
from capability_commons.services.review import ReviewService

router = APIRouter()


@router.post("/reviews", response_model=ReviewResponse)
async def submit_review(request: CreateReviewRequest, session: DBSession, workspace: CurrentWorkspace) -> ReviewResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = ReviewService(session)
    review = await service.submit_review(**data)
    return ReviewResponse.model_validate(review, from_attributes=True)


@router.post("/contradictions", response_model=ContradictionResponse)
async def open_contradiction(request: OpenContradictionRequest, session: DBSession, workspace: CurrentWorkspace) -> ContradictionResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = ReviewService(session)
    contradiction = await service.open_contradiction(**data)
    return ContradictionResponse.model_validate(contradiction, from_attributes=True)


@router.post("/contradictions/{id}/resolve", response_model=ContradictionResponse)
async def resolve_contradiction(id: uuid.UUID, request: ResolveContradictionRequest, session: DBSession, workspace: CurrentWorkspace) -> ContradictionResponse:
    service = ReviewService(session)
    contradiction = await service.resolve_contradiction(id, **request.model_dump())
    return ContradictionResponse.model_validate(contradiction, from_attributes=True)


@router.post("/objects/{object_id}/versions/{version_id}/verify", response_model=VersionValidityActionResponse)
async def verify_version(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession, workspace: CurrentWorkspace) -> VersionValidityActionResponse:
    review = ReviewService(session)
    await review.mark_verified(object_id, version_id)
    registry = RegistryService(session)
    version = await registry.get_version(version_id)
    return VersionValidityActionResponse(object_id=object_id, version_id=version_id, validity_status=version.validity_status)


@router.post("/objects/{object_id}/versions/{version_id}/dispute", response_model=VersionValidityActionResponse)
async def dispute_version(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession, workspace: CurrentWorkspace) -> VersionValidityActionResponse:
    review = ReviewService(session)
    await review.mark_disputed(object_id, version_id)
    registry = RegistryService(session)
    version = await registry.get_version(version_id)
    return VersionValidityActionResponse(object_id=object_id, version_id=version_id, validity_status=version.validity_status)


@router.post("/objects/{object_id}/versions/{version_id}/deprecate", response_model=VersionValidityActionResponse)
async def deprecate_version(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession, workspace: CurrentWorkspace) -> VersionValidityActionResponse:
    review = ReviewService(session)
    await review.propose_deprecation(object_id, version_id)
    registry = RegistryService(session)
    version = await registry.get_version(version_id)
    return VersionValidityActionResponse(object_id=object_id, version_id=version_id, validity_status=version.validity_status)


@router.get("/reviews/queue")
async def review_queue(
    session: DBSession,
    workspace: CurrentWorkspace,
    lifecycle_state: list[LifecycleState] | None = Query(default=None),
    risk_band: list[RiskBand] | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List objects awaiting review (REV-2 — filters by state + risk).

    Defaults to IN_REVIEW objects of all risks. Pass ?lifecycle_state=
    multiple times to widen (e.g. include `reviewed`). Pass ?risk_band=
    to narrow to high-risk content, which is the safety-review queue.
    The response includes the current_version_id so the UI can hit
    /publish-check on demand.
    """
    states = lifecycle_state or [LifecycleState.IN_REVIEW]
    stmt = (
        select(ContextObject, ContextObjectVersion)
        .join(
            ContextObjectVersion,
            ContextObject.current_version_id == ContextObjectVersion.id,
            isouter=True,
        )
        .where(
            ContextObject.workspace_id == workspace.id,
            ContextObject.lifecycle_state.in_(states),
        )
    )
    if risk_band:
        stmt = stmt.where(ContextObjectVersion.risk_band.in_(risk_band))
    stmt = (
        stmt.order_by(ContextObject.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(obj.id),
            "object_id": str(obj.id),
            "slug": obj.slug,
            "type": obj.type.value,
            "canonical_title": obj.canonical_title,
            "lifecycle_state": obj.lifecycle_state.value,
            "updated_at": obj.updated_at.isoformat(),
            "current_version_id": str(obj.current_version_id) if obj.current_version_id else None,
            "risk_band": version.risk_band.value if version and version.risk_band else None,
            "difficulty": version.difficulty if version else None,
        }
        for obj, version in rows
    ]
