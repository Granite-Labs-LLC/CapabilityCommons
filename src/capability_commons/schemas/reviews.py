from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from capability_commons.domain.enums import (
    ContradictionDimension,
    ContradictionStatus,
    ReviewOutcome,
    ReviewType,
    SeverityLevel,
    ValidityStatus,
)


class CreateReviewRequest(BaseModel):
    workspace_id: uuid.UUID
    context_object_version_id: uuid.UUID
    review_type: ReviewType
    outcome: ReviewOutcome
    reviewer_id: uuid.UUID | None = None
    commentary: str | None = None
    checklist: dict[str, Any] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    context_object_version_id: uuid.UUID
    review_type: ReviewType
    outcome: ReviewOutcome
    reviewer_id: uuid.UUID | None = None
    commentary: str | None = None
    checklist: dict[str, Any]
    created_at: datetime


class OpenContradictionRequest(BaseModel):
    workspace_id: uuid.UUID
    left_version_id: uuid.UUID
    right_version_id: uuid.UUID
    dimension: ContradictionDimension
    severity: SeverityLevel = SeverityLevel.MEDIUM
    opened_by: uuid.UUID | None = None


class ResolveContradictionRequest(BaseModel):
    resolved_by: uuid.UUID | None = None
    resolution_note: str
    resolution_version_id: uuid.UUID | None = None
    status: ContradictionStatus = ContradictionStatus.RESOLVED


class ContradictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    left_version_id: uuid.UUID
    right_version_id: uuid.UUID
    dimension: ContradictionDimension
    severity: SeverityLevel
    status: ContradictionStatus
    opened_by: uuid.UUID | None = None
    opened_at: datetime
    resolved_by: uuid.UUID | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    resolution_version_id: uuid.UUID | None = None


class VersionValidityActionResponse(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID
    validity_status: ValidityStatus
