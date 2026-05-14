"""Schemas for audit event API responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from capability_commons.domain.enums import AuditEventType


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    event_type: AuditEventType
    actor_key_id: uuid.UUID | None = None
    target_object_id: uuid.UUID | None = None
    target_version_id: uuid.UUID | None = None
    target_edge_id: uuid.UUID | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime
