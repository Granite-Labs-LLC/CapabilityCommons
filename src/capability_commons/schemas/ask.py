from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from capability_commons.domain.enums import RetrievalIntent


class AskContext(BaseModel):
    """User's situational context for filtering and ranking."""
    housing_type: str | None = None
    climate_zone: str | None = None
    budget_profile: str | None = None
    experience_level: str | None = None
    settlement_type: str | None = None


class AskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    intent: RetrievalIntent | None = Field(None, description="If null, auto-detected from query")
    context: AskContext | None = None
    conversation_id: uuid.UUID | None = None
    max_results: int = Field(default=8, ge=1, le=50)


class ImplementationStep(BaseModel):
    step: int
    action: str
    tools: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    time_estimate: str | None = None
    source_slug: str | None = None


class SafetyBlock(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    when_to_get_help: list[str] = Field(default_factory=list)


class AskCitation(BaseModel):
    source_title: str
    slug: str
    excerpt: str
    page_range: str | None = None
    support_strength: str = "moderate"


class RelatedObject(BaseModel):
    slug: str
    title: str
    role: str = "related"


class AskResponse(BaseModel):
    answer: str
    action_now: str | None = None
    implementation_plan: list[ImplementationStep] = Field(default_factory=list)
    safety: SafetyBlock = Field(default_factory=SafetyBlock)
    citations: list[AskCitation] = Field(default_factory=list)
    related_objects: list[RelatedObject] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    resolved_intent: RetrievalIntent
    conversation_id: uuid.UUID | None = None
    retrieval_run_id: uuid.UUID | None = None
