from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from capability_commons.schemas.common import CitationSnippet


class PublicImplementationProfile(BaseModel):
    """UI-friendly projection of implementation profile fields."""
    smallest_viable_version: str | None = None
    preflight_checks: list[str] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list, description="Tiered tools with substitutes")
    materials: list[dict[str, Any]] = Field(default_factory=list, description="Tiered materials with substitutes")
    estimated_time_hours: float | None = None
    estimated_cost_band: str | None = None
    success_checks: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    escalation_guidance: str | None = None


def project_implementation_profile(structured_data: dict[str, Any]) -> PublicImplementationProfile | None:
    """Extract an implementation profile projection from structured_data.

    Merges top-level fields (tools, materials, stop_conditions, variants)
    with nested implementation_profile fields. Returns None if no
    actionable fields are found.
    """
    profile_data = structured_data.get("implementation_profile", {}) or {}

    # Merge: prefer implementation_profile, fall back to top-level
    tools = profile_data.get("tools_tiered", [])
    if not tools:
        raw_tools = structured_data.get("tools", [])
        tools = [{"name": t, "tier": "unspecified"} for t in raw_tools] if raw_tools else []

    materials = profile_data.get("materials_tiered", [])
    if not materials:
        raw_materials = structured_data.get("materials", [])
        materials = [{"name": m, "tier": "unspecified"} for m in raw_materials] if raw_materials else []

    stop_conditions = profile_data.get("stop_conditions", []) or structured_data.get("stop_conditions", [])
    variants = profile_data.get("variants", []) or structured_data.get("variants", [])
    success_checks = profile_data.get("success_checks", []) or structured_data.get("success_criteria", [])

    result = PublicImplementationProfile(
        smallest_viable_version=profile_data.get("smallest_viable_version"),
        preflight_checks=profile_data.get("preflight_checks", []),
        tools=tools,
        materials=materials,
        estimated_time_hours=profile_data.get("estimated_time_hours"),
        estimated_cost_band=profile_data.get("estimated_cost_band"),
        success_checks=success_checks,
        stop_conditions=stop_conditions,
        common_mistakes=profile_data.get("common_mistakes", []),
        variants=variants,
        escalation_guidance=profile_data.get("escalation_guidance"),
    )

    # Return None if all fields are empty/None
    has_content = (
        result.smallest_viable_version
        or result.preflight_checks
        or result.tools
        or result.materials
        or result.estimated_time_hours
        or result.success_checks
        or result.stop_conditions
        or result.escalation_guidance
    )
    return result if has_content else None


class PublicObjectResponse(BaseModel):
    slug: str
    title: str
    type: str
    summary_short: str | None = None
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    implementation_profile: PublicImplementationProfile | None = None
    facets: dict[str, list[str]] = Field(default_factory=dict)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[CitationSnippet] = Field(default_factory=list)
    review_summary: dict[str, int] = Field(default_factory=dict)
    contradiction_summary: dict[str, int] = Field(default_factory=dict)
    members: list[dict[str, Any]] = Field(default_factory=list)


class PublicBundleResponse(BaseModel):
    object: PublicObjectResponse
    bundle: dict[str, Any] = Field(default_factory=dict)
