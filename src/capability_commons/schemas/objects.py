from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from capability_commons.domain.enums import (
    COType,
    CostBand,
    LifecycleState,
    ReadingLevel,
    RiskBand,
    StageType,
    ValidityStatus,
    VisibilityType,
)
from capability_commons.schemas.common import EntityAssignment, FacetAssignment


class CreateObjectRequest(BaseModel):
    workspace_id: uuid.UUID
    slug: str
    type: COType
    canonical_title: str
    visibility: VisibilityType = VisibilityType.PUBLIC
    default_language: str = "en"


class ObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    type: COType
    canonical_title: str
    current_version_id: uuid.UUID | None = None
    lifecycle_state: LifecycleState
    visibility: VisibilityType
    default_language: str
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    archived_at: datetime | None = None


class CreateVersionRequest(BaseModel):
    title: str
    summary_short: str | None = None
    summary_medium: str | None = None
    summary_long: str | None = None
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    validity_status: ValidityStatus = ValidityStatus.CURRENT
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    stage: StageType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    cost_band: CostBand = CostBand.FREE
    risk_band: RiskBand = RiskBand.LOW
    reading_level: ReadingLevel = ReadingLevel.GENERAL
    beginner_safe: bool = True
    teach_forward_ready: bool = False
    requires_professional: bool = False
    source_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    evidence_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    locale_scope: str = "global"
    language_code: str = "en"
    supersedes_version_id: uuid.UUID | None = None
    checksum: str | None = None


class UpdateVersionRequest(BaseModel):
    title: str | None = None
    summary_short: str | None = None
    summary_medium: str | None = None
    summary_long: str | None = None
    plain_language: str | None = None
    markdown_body: str | None = None
    structured_data: dict[str, Any] | None = None
    validity_status: ValidityStatus | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    stage: StageType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, gt=0)
    cost_band: CostBand | None = None
    risk_band: RiskBand | None = None
    reading_level: ReadingLevel | None = None
    beginner_safe: bool | None = None
    teach_forward_ready: bool | None = None
    requires_professional: bool | None = None
    source_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    evidence_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    locale_scope: str | None = None
    language_code: str | None = None
    checksum: str | None = None


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    context_object_id: uuid.UUID
    version_no: int
    title: str
    summary_short: str | None = None
    summary_medium: str | None = None
    summary_long: str | None = None
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any]
    validity_status: ValidityStatus
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    stage: StageType | None = None
    difficulty: int | None = None
    estimated_minutes: int | None = None
    cost_band: CostBand
    risk_band: RiskBand
    reading_level: ReadingLevel
    beginner_safe: bool
    teach_forward_ready: bool
    requires_professional: bool
    source_confidence: Decimal | None = None
    evidence_confidence: Decimal | None = None
    locale_scope: str
    language_code: str
    supersedes_version_id: uuid.UUID | None = None
    checksum: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime


class VersionDetailResponse(VersionResponse):
    facets: list[FacetAssignment] = Field(default_factory=list)
    entities: list[EntityAssignment] = Field(default_factory=list)
    review_count: int = 0


class AttachFacetsRequest(BaseModel):
    facets: list[FacetAssignment]


class AttachEntitiesRequest(BaseModel):
    entities: list[EntityAssignment]


class VersionListResponse(BaseModel):
    object_id: uuid.UUID
    versions: list[VersionResponse]


class PublishVersionResponse(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID
    lifecycle_state: LifecycleState
    current_version_id: uuid.UUID
    published_at: datetime


class CurrentVersionResponse(BaseModel):
    object: ObjectResponse
    version: VersionDetailResponse


class ObjectVersionsEnvelope(BaseModel):
    object: ObjectResponse
    versions: list[VersionResponse]


class CreateEntityRequest(BaseModel):
    workspace_id: uuid.UUID
    entity_type: str
    canonical_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddAliasRequest(BaseModel):
    alias: str
