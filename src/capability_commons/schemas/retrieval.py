from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from capability_commons.domain.enums import RetrievalIntent, RetrievalRunStatus, RetrievalStepType
from capability_commons.schemas.common import CitationSnippet
from capability_commons.schemas.search import PublicSearchFilters


class RetrievalBudgets(BaseModel):
    max_latency_ms: int = Field(default=5000, ge=100)
    max_iterations: int = Field(default=4, ge=1, le=10)
    max_search_results: int = Field(default=80, ge=1, le=500)
    max_graph_depth: int = Field(default=3, ge=1, le=6)
    max_segments: int = Field(default=40, ge=1, le=200)
    max_model_calls: int = Field(default=2, ge=0, le=20)


class RequiredEvidence(BaseModel):
    must_cite_sources: bool = True
    min_reviewed_objects: int = Field(default=2, ge=0, le=20)
    prefer_verified: bool = True


class RetrievalRequest(BaseModel):
    workspace_id: uuid.UUID | None = None
    requester_id: uuid.UUID | None = None
    query: str
    # Optional: when omitted (or sent as null), the service infers intent
    # from the query text via `infer_intent`.
    intent: RetrievalIntent | None = None
    facet_filters: dict[str, list[str]] = Field(default_factory=dict)
    # UI-parity attribute filters: difficulty_max, stage, beginner_safe,
    # risk_band, cost_band. Applied as SQL predicates by the search adapter.
    attribute_filters: PublicSearchFilters | None = None
    seed_object_ids: list[uuid.UUID] = Field(default_factory=list)
    seed_entity_ids: list[uuid.UUID] = Field(default_factory=list)
    budgets: RetrievalBudgets = Field(default_factory=RetrievalBudgets)
    required_evidence: RequiredEvidence = Field(default_factory=RequiredEvidence)
    output_mode: str = "public_answer"


class RetrievalPlan(BaseModel):
    intent: RetrievalIntent
    search_top_k: int
    graph_depth: int
    iteration_limit: int
    edge_types: list[str]
    rerank_weights: dict[str, float]


class EvidenceNode(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID
    slug: str
    title: str
    type: str
    score: float | Decimal
    summary_short: str | None = None
    citations: list[CitationSnippet] = Field(default_factory=list)
    rationale: str | None = None
    # Carries structured_data.implementation when the source object is a
    # skill_guide / project_blueprint, so the answer composer can populate
    # action_now / implementation_plan / safety from typed fields rather
    # than scraping markdown (PLAN retrieval P1-8).
    structured_data: dict[str, Any] | None = None


class RetrievalStepResponse(BaseModel):
    id: uuid.UUID
    retrieval_run_id: uuid.UUID
    iteration_no: int
    step_type: RetrievalStepType
    query_text: str | None = None
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    latency_ms: int | None = None
    budget_spent: dict[str, Any]
    created_at: datetime


class RetrievalRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    requester_id: uuid.UUID | None = None
    intent: RetrievalIntent
    query_text: str
    task_spec: dict[str, Any]
    compiled_plan: dict[str, Any]
    status: RetrievalRunStatus
    sufficiency_score: float | Decimal
    budget_snapshot: dict[str, Any]
    result_summary: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None = None


class EvidencePackResponse(BaseModel):
    run_id: uuid.UUID
    intent: RetrievalIntent
    query: str
    plan: RetrievalPlan
    sufficiency_score: float | Decimal
    evidence: list[EvidenceNode]
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    next_steps: list[dict[str, Any]] = Field(default_factory=list)
    rendered_markdown: str | None = None
