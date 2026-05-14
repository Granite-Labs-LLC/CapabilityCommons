from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from capability_commons.domain.enums import COType, LifecycleState


class PublicSearchFilters(BaseModel):
    """UX-friendly search filters for the public interface."""
    stage: str | None = Field(None, description="foundation, household, productive, community, advanced")
    difficulty_max: int | None = Field(None, ge=1, le=5, description="Max difficulty (1=easiest, 5=hardest)")
    cost_band: str | None = Field(None, description="free, low, medium, high")
    risk_band: str | None = Field(None, description="low, moderate, high, expert_only")
    beginner_safe: bool | None = Field(None, description="Filter to beginner-safe content only")
    housing_type: str | None = Field(None, description="apartment, house, mobile_home, etc.")
    climate_zone: str | None = Field(None, description="tropical, arid, temperate, cold")
    settlement_type: str | None = Field(None, description="urban, suburban, rural, remote")
    # MULTI-1: language scaffold. Backend is English-only today but this
    # column on context_object_versions exists; once non-English content
    # lands we filter for it without another schema bump.
    language_code: str | None = Field(None, description="ISO 639-1 (e.g. 'en', 'es'); null = any")

    def to_facet_filters(self) -> dict[str, list[str]]:
        """Convert UX filters to internal facet_filters dict."""
        filters: dict[str, list[str]] = {}
        if self.housing_type:
            filters["housing_type"] = [self.housing_type]
        if self.climate_zone:
            filters["climate_zone"] = [self.climate_zone]
        if self.settlement_type:
            filters["settlement_type"] = [self.settlement_type]
        if self.stage:
            filters["stage"] = [self.stage]
        if self.cost_band:
            filters["budget_profile"] = [self.cost_band]
        return filters


class SearchRequest(BaseModel):
    workspace_id: uuid.UUID | None = None
    query: str
    facet_filters: dict[str, list[str]] = Field(default_factory=dict)
    filters: PublicSearchFilters | None = Field(None, description="UX-friendly filters (merged with facet_filters)")
    object_types: list[COType] = Field(default_factory=list)
    only_published: bool = True
    top_k: int = Field(default=20, ge=1, le=200)

    def resolved_facet_filters(self) -> dict[str, list[str]]:
        """Merge UX filters with raw facet_filters."""
        result = dict(self.facet_filters)
        if self.filters:
            for key, values in self.filters.to_facet_filters().items():
                existing = result.get(key, [])
                result[key] = list(set(existing + values))
        return result


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
    facets: dict[str, list[str]] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    top_k: int
    hits: list[SearchHit]
