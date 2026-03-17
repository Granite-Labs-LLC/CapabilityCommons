from __future__ import annotations

import uuid

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.domain.enums import EntityType
from capability_commons.schemas.objects import AddAliasRequest, CreateEntityRequest
from capability_commons.services.entities import EntityService

router = APIRouter()


@router.post("/entities")
async def create_entity(request: CreateEntityRequest, session: DBSession, workspace: CurrentWorkspace) -> dict:
    service = EntityService(session)
    entity = await service.create_entity(
        workspace_id=workspace.id,
        entity_type=EntityType(request.entity_type),
        canonical_name=request.canonical_name,
        metadata=request.metadata,
    )
    return {
        "id": entity.id,
        "workspace_id": entity.workspace_id,
        "entity_type": entity.entity_type.value,
        "canonical_name": entity.canonical_name,
        "metadata": entity.metadata_json,
    }


@router.post("/entities/{entity_id}/aliases")
async def add_alias(entity_id: uuid.UUID, request: AddAliasRequest, session: DBSession) -> dict:
    service = EntityService(session)
    alias = await service.add_alias(entity_id, request.alias)
    return {"id": alias.id, "entity_id": alias.entity_id, "alias": alias.alias}
