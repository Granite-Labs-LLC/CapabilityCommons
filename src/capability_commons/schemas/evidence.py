from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from capability_commons.domain.enums import EvidenceSourceKind, TrustTier


class CreateEvidenceSourceRequest(BaseModel):
    workspace_id: uuid.UUID
    source_kind: EvidenceSourceKind
    title: str
    uri: str | None = None
    citation_text: str | None = None
    trust_tier: TrustTier = TrustTier.SECONDARY
    license: str | None = None
    language_code: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    source_kind: EvidenceSourceKind
    title: str
    uri: str | None = None
    citation_text: str | None = None
    trust_tier: TrustTier
    license: str | None = None
    language_code: str
    created_at: datetime


class CreateEvidenceSpanRequest(BaseModel):
    source_id: uuid.UUID
    context_object_version_id: uuid.UUID | None = None
    segment_id: uuid.UUID | None = None
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    excerpt: str
    checksum: str | None = None


class EvidenceSpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    context_object_version_id: uuid.UUID | None = None
    segment_id: uuid.UUID | None = None
    start_char: int
    end_char: int
    excerpt: str
    checksum: str | None = None
    created_at: datetime


class EdgeCitationRequest(BaseModel):
    edge_id: uuid.UUID
    evidence_span_id: uuid.UUID


class CitationResponse(BaseModel):
    source_id: uuid.UUID
    source_title: str
    evidence_span_id: uuid.UUID
    excerpt: str
    start_char: int
    end_char: int
    uri: str | None = None
