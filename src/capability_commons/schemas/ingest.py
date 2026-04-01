"""API schemas for ingest job endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from capability_commons.domain.enums import IngestJobStatus, IngestPassStatus


class CreateIngestJobRequest(BaseModel):
    project_name: str
    source_count: int = 0
    config: dict[str, Any] = {}


class IngestJobPassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    pass_name: str
    ordinal: int
    status: IngestPassStatus
    output_path: str | None = None
    artifact_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IngestJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_name: str
    status: IngestJobStatus
    source_count: int
    config_json: dict[str, Any]
    error_log: str | None = None
    created_at: datetime
    created_by: uuid.UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    passes: list[IngestJobPassResponse] = []
