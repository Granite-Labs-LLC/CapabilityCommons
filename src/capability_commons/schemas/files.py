"""Schemas for file attachment API responses."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_store_key: str
    media_type: str
    byte_size: int | None = None
    checksum: str | None = None
    label: str | None = None
    created_at: datetime
