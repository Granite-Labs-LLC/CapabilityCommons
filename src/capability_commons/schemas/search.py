from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from capability_commons.domain.enums import COType, LifecycleState


class SearchRequest(BaseModel):
    workspace_id: uuid.UUID
    query: str
    facet_filters: dict[str, list[str]] = Field(default_factory=dict)
    object_types: list[COType] = Field(default_factory=list)
    only_published: bool = True
    top_k: int = Field(default=20, ge=1, le=200)


class SearchHit(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID
    slug: str
    type: COType
    title: str
    summary_short: str | None = None
    plain_language: str
    score: float | Decimal
    lifecycle_state: LifecycleState
    validity_status: str
    matched_facets: dict[str, list[str]] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    top_k: int
    hits: list[SearchHit]
