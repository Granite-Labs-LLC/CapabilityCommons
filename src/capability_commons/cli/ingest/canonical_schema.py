"""Canonical draft schema -- the release gate for Pass 2 output."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

VALID_CO_TYPES = {
    "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
    "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
    "field_report", "worksheet", "glossary", "safety_notice", "correction",
    "expert_review", "translation", "community_map", "resource_directory",
}


class CanonicalDraft(BaseModel, extra="allow"):
    """Full schema for a canonical draft object produced by Pass 2.

    This enforces the fields that downstream passes (cite, canonicalize,
    edges, load) depend on.
    """
    id: str
    slug: str
    co_type: str
    canonical_title: str
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any] = {}
    version_no: int = 1
    lifecycle_state: str = "draft"
    visibility: str = "public"
    language_code: str = "en"
    primary_domain: str = ""
    secondary_domains: list[str] = []
    stage: str = ""
    contexts: list[str] = []
    difficulty: int | None = None
    cost_band: str = "free"
    risk_band: str = "low"
    summary_short: str = ""
    summary_medium: str = ""
    requires: list = []
    suggested_edges: list = []
    citations: list = []
    source_segment_ids: list[str] = []

    @field_validator("co_type")
    @classmethod
    def validate_co_type(cls, v: str) -> str:
        normalized = v.lower().replace(" ", "_")
        if normalized not in VALID_CO_TYPES:
            raise ValueError(f"Invalid co_type: {v}")
        return normalized
