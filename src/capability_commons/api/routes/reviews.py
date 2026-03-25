from __future__ import annotations

import uuid

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
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
