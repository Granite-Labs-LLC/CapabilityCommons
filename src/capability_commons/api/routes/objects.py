from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
from capability_commons.schemas.objects import (
    AttachEntitiesRequest,
    AttachFacetsRequest,
    CreateObjectRequest,
    CreateVersionRequest,
    CurrentVersionResponse,
    ObjectResponse,
    ObjectVersionsEnvelope,
    PublishVersionResponse,
    UpdateVersionRequest,
    VersionDetailResponse,
    VersionListResponse,
    VersionResponse,
)
from capability_commons.schemas.pagination import PaginatedResponse, PaginationParams
from capability_commons.services.publish_gate import PublishGate
from capability_commons.services.registry import RegistryService

router = APIRouter()


def _version_detail(version) -> VersionDetailResponse:
    return VersionDetailResponse(
        **VersionResponse.model_validate(version, from_attributes=True).model_dump(),
        facets=[{"facet_type": facet.facet_type.value, "facet_value": facet.facet_value} for facet in version.facets],
        entities=[
            {
                "entity_id": link.entity_id,
                "mention_count": link.mention_count,
                "role_label": link.role_label,
                "is_primary": link.is_primary,
            }
            for link in version.entities
        ],
        review_count=len(version.review_records),
    )


@router.get("/objects", response_model=PaginatedResponse[ObjectResponse])
async def list_objects(
    workspace: CurrentWorkspace,
    session: DBSession,
    cursor: str | None = None,
    limit: int = 20,
) -> PaginatedResponse[ObjectResponse]:
    params = PaginationParams(cursor=cursor, limit=min(limit, 100))
    service = RegistryService(session)
    objects, total = await service.list_objects(
        workspace.id, cursor_id=params.decode_cursor(), limit=params.limit,
    )
    items = objects[:params.limit]
    has_more = len(objects) > params.limit
    next_cursor = PaginatedResponse.encode_cursor(items[-1].id) if has_more and items else None
    return PaginatedResponse(
        items=[ObjectResponse.model_validate(obj, from_attributes=True) for obj in items],
        next_cursor=next_cursor,
        total_count=total,
    )


@router.post("/objects", response_model=ObjectResponse)
async def create_object(request: CreateObjectRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> ObjectResponse:
    request.workspace_id = workspace.id
    service = RegistryService(session)
    obj = await service.create_object(request, actor_id=actor_id)
    return ObjectResponse.model_validate(obj, from_attributes=True)


@router.post("/objects/{object_id}/versions", response_model=VersionResponse)
async def create_version(object_id: uuid.UUID, request: CreateVersionRequest, session: DBSession, actor_id: ActorID) -> VersionResponse:
    service = RegistryService(session)
    version = await service.create_version(object_id, request, actor_id=actor_id)
    return VersionResponse.model_validate(version, from_attributes=True)


@router.patch("/objects/{object_id}/versions/{version_id}", response_model=VersionResponse)
async def update_version(object_id: uuid.UUID, version_id: uuid.UUID, request: UpdateVersionRequest, session: DBSession) -> VersionResponse:
    service = RegistryService(session)
    version = await service.update_draft_version(object_id, version_id, request)
    return VersionResponse.model_validate(version, from_attributes=True)


@router.post("/objects/{object_id}/versions/{version_id}/publish", response_model=PublishVersionResponse)
async def publish_version(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession) -> PublishVersionResponse:
    service = RegistryService(session)
    obj = await service.publish_version(object_id, version_id)
    return PublishVersionResponse(
        object_id=obj.id,
        version_id=version_id,
        lifecycle_state=obj.lifecycle_state,
        current_version_id=obj.current_version_id,
        published_at=obj.published_at,
    )


@router.get("/objects/{object_id}/versions/{version_id}/publish-check")
async def publish_check(object_id: uuid.UUID, version_id: uuid.UUID, session: DBSession):
    """Dry-run publish gate check without actually publishing."""
    service = RegistryService(session)
    obj = await service.get_object(object_id)
    version = await service.get_version(version_id)
    gate = PublishGate(session)
    result = await gate.check(version, obj.type)
    return {
        "passed": result.passed,
        "blockers": result.blockers,
        "warnings": result.warnings,
    }


@router.post("/objects/{object_id}/versions/{version_id}/facets", response_model=VersionDetailResponse)
async def attach_facets(object_id: uuid.UUID, version_id: uuid.UUID, request: AttachFacetsRequest, session: DBSession) -> VersionDetailResponse:
    service = RegistryService(session)
    version = await service.attach_facets(object_id, version_id, [facet.model_dump() for facet in request.facets])
    await session.refresh(version, attribute_names=["facets", "entities", "review_records"])
    return _version_detail(version)


@router.post("/objects/{object_id}/versions/{version_id}/entities", response_model=VersionDetailResponse)
async def attach_entities(object_id: uuid.UUID, version_id: uuid.UUID, request: AttachEntitiesRequest, session: DBSession) -> VersionDetailResponse:
    service = RegistryService(session)
    version = await service.attach_entities(object_id, version_id, [entity.model_dump() for entity in request.entities])
    await session.refresh(version, attribute_names=["facets", "entities", "review_records"])
    return _version_detail(version)


@router.get("/objects/{object_id}", response_model=ObjectResponse)
async def get_object(object_id: uuid.UUID, session: DBSession) -> ObjectResponse:
    service = RegistryService(session)
    obj = await service.get_object(object_id)
    return ObjectResponse.model_validate(obj, from_attributes=True)


@router.get("/objects/{object_id}/versions", response_model=ObjectVersionsEnvelope)
async def list_versions(object_id: uuid.UUID, session: DBSession) -> ObjectVersionsEnvelope:
    service = RegistryService(session)
    obj = await service.get_object(object_id)
    versions = await service.list_versions(object_id)
    return ObjectVersionsEnvelope(
        object=ObjectResponse.model_validate(obj, from_attributes=True),
        versions=[VersionResponse.model_validate(version, from_attributes=True) for version in versions],
    )


@router.get("/objects/{object_id}/current", response_model=CurrentVersionResponse)
async def get_current_version(object_id: uuid.UUID, session: DBSession) -> CurrentVersionResponse:
    service = RegistryService(session)
    obj = await service.get_object(object_id)
    version = await service.get_current(object_id)
    await session.refresh(version, attribute_names=["facets", "entities", "review_records"])
    return CurrentVersionResponse(
        object=ObjectResponse.model_validate(obj, from_attributes=True),
        version=_version_detail(version),
    )
