from __future__ import annotations

from fastapi import APIRouter

from capability_commons.api.deps import DBSession
from capability_commons.publication.service import PublicationService
from capability_commons.schemas.public import PublicBundleResponse, PublicObjectResponse

router = APIRouter()


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
