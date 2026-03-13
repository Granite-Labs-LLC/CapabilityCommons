from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "capability_commons"


class FacetAssignment(BaseModel):
    facet_type: str
    facet_value: str


class EntityAssignment(BaseModel):
    entity_id: uuid.UUID
    mention_count: int = Field(default=1, ge=1)
    role_label: str | None = None
    is_primary: bool = False


class OutboxResponse(BaseModel):
    event_count: int = 0


class AuditMeta(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PageInfo(BaseModel):
    total: int
    limit: int
    offset: int


class CitationSnippet(BaseModel):
    evidence_span_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    excerpt: str
    start_char: int
    end_char: int


class SimpleObjectRef(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID | None = None
    slug: str | None = None
    title: str | None = None
    type: str | None = None
    score: float | Decimal | None = None


JSONDict = dict[str, Any]
