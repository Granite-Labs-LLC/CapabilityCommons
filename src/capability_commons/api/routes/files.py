"""File attachment API routes."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.config import get_settings
from capability_commons.db.models import ObjectFile
from capability_commons.schemas.files import FileMetadataResponse
from capability_commons.storage.adapters import LocalStorageAdapter, StorageAdapter

router = APIRouter()

ALLOWED_MEDIA_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf", "text/plain", "text/markdown", "text/csv",
}


def get_storage_adapter() -> StorageAdapter:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorageAdapter(root=settings.storage_root)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


@router.post(
    "/objects/{object_id}/versions/{version_id}/files",
    response_model=FileMetadataResponse,
    status_code=201,
)
async def upload_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file: UploadFile,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
    label: str | None = None,
) -> FileMetadataResponse:
    settings = get_settings()

    media_type = file.content_type or "application/octet-stream"
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            415,
            f"Media type not allowed: {media_type}. Allowed: {sorted(ALLOWED_MEDIA_TYPES)}",
        )

    data = await file.read()
    if len(data) > settings.storage_max_file_size:
        raise HTTPException(
            413,
            f"File too large. Maximum size: {settings.storage_max_file_size} bytes",
        )

    checksum = hashlib.sha256(data).hexdigest()
    key = uuid.uuid4().hex

    storage.put(key, data, media_type)

    obj_file = ObjectFile(
        context_object_version_id=version_id,
        object_store_key=key,
        media_type=media_type,
        byte_size=len(data),
        checksum=checksum,
        label=label,
    )
    session.add(obj_file)
    await session.flush()
    await session.commit()
    await session.refresh(obj_file)
    return FileMetadataResponse.model_validate(obj_file, from_attributes=True)


@router.get(
    "/objects/{object_id}/versions/{version_id}/files",
    response_model=list[FileMetadataResponse],
)
async def list_files(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> list[FileMetadataResponse]:
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.context_object_version_id == version_id)
    )
    files = list(result.scalars().all())
    return [FileMetadataResponse.model_validate(f, from_attributes=True) for f in files]


@router.get("/objects/{object_id}/versions/{version_id}/files/{file_id}")
async def download_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
) -> Response:
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.id == file_id)
    )
    obj_file = result.scalar_one_or_none()
    if not obj_file:
        raise HTTPException(404, "File not found")

    try:
        data = storage.get(obj_file.object_store_key)
    except FileNotFoundError:
        raise HTTPException(404, "File data not found in storage")

    return Response(content=data, media_type=obj_file.media_type)


@router.delete(
    "/objects/{object_id}/versions/{version_id}/files/{file_id}",
    status_code=204,
)
async def delete_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
) -> None:
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.id == file_id)
    )
    obj_file = result.scalar_one_or_none()
    if not obj_file:
        raise HTTPException(404, "File not found")

    try:
        storage.delete(obj_file.object_store_key)
    except FileNotFoundError:
        pass

    await session.delete(obj_file)
    await session.commit()
