from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from capability_commons.schemas.common import CitationSnippet


class ImplementationVariant(BaseModel):
    """One contextual variant of a how-to (renter, low-budget, off-grid, …).

    Matches the ingest envelope shape produced by Pass 2 (draft).
    """
    label: str
    when: str
    notes: str | None = None


class PublicImplementationProfile(BaseModel):
    """UI-friendly projection of the "can I do this now?" envelope.

    Matches the ingest-pass shape stored under
    `structured_data["implementation"]` (PLAN P1-9). When the backend
    encounters legacy seed YAML that used `implementation_profile` with
    `tools_tiered` / `estimated_time_hours` etc., `project_implementation_profile`
    coerces it into this shape for the public surface.
    """
    smallest_viable_version: str | None = None
    tools: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    expected_time: str | None = None
    expected_cost: str | None = None
    success_checks: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    variants: list[ImplementationVariant] = Field(default_factory=list)
    when_to_escalate: list[str] = Field(default_factory=list)


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def _coerce_variants(value: Any) -> list[ImplementationVariant]:
    """Variants come in two shapes:
        a) the ingest envelope: [{label, when, notes?}, ...]
        b) legacy seed YAML: ["renter", "low_budget", ...] (bare strings).
    Both are normalized into ImplementationVariant rows.
    """
    if not isinstance(value, list):
        return []
    out: list[ImplementationVariant] = []
    for v in value:
        if isinstance(v, dict) and v.get("label"):
            out.append(ImplementationVariant(
                label=str(v["label"]),
                when=str(v.get("when") or ""),
                notes=v.get("notes"),
            ))
        elif isinstance(v, str) and v.strip():
            out.append(ImplementationVariant(label=v, when=""))
    return out


def project_implementation_profile(
    structured_data: dict[str, Any],
) -> PublicImplementationProfile | None:
    """Extract a public envelope projection from structured_data.

    Resolution order:
      1. `structured_data["implementation"]` — ingest-pass shape (current).
      2. `structured_data["implementation_profile"]` — legacy seed shape.
      3. Top-level `tools`, `materials`, `stop_conditions`, `variants` as
         a final fallback for very old seed YAML.

    Returns None when nothing actionable can be assembled.
    """
    impl = structured_data.get("implementation") or {}
    legacy = structured_data.get("implementation_profile") or {}

    # Pull each field from the highest-priority source that has it.
    tools = _coerce_str_list(
        impl.get("tools")
        or [t.get("name") if isinstance(t, dict) else t for t in legacy.get("tools_tiered", []) or []]
        or structured_data.get("tools", [])
    )
    materials = _coerce_str_list(
        impl.get("materials")
        or [m.get("name") if isinstance(m, dict) else m for m in legacy.get("materials_tiered", []) or []]
        or structured_data.get("materials", [])
    )
    success_checks = _coerce_str_list(
        impl.get("success_checks")
        or legacy.get("success_checks")
        or structured_data.get("success_criteria")
    )
    stop_conditions = _coerce_str_list(
        impl.get("stop_conditions")
        or legacy.get("stop_conditions")
        or structured_data.get("stop_conditions")
    )
    common_mistakes = _coerce_str_list(
        impl.get("common_mistakes") or legacy.get("common_mistakes")
    )
    variants = _coerce_variants(
        impl.get("variants") or legacy.get("variants") or structured_data.get("variants")
    )

    # Legacy stored time as float hours; coerce to a human string.
    expected_time = impl.get("expected_time")
    if not expected_time and legacy.get("estimated_time_hours") is not None:
        hours = legacy["estimated_time_hours"]
        plural = "s" if float(hours) != 1.0 else ""
        expected_time = f"{hours} hour{plural}"

    expected_cost = impl.get("expected_cost") or legacy.get("estimated_cost_band")

    # Legacy stored escalation as a single string; ingest stores a list.
    when_to_escalate = _coerce_str_list(impl.get("when_to_escalate"))
    if not when_to_escalate and legacy.get("escalation_guidance"):
        when_to_escalate = [str(legacy["escalation_guidance"])]

    profile = PublicImplementationProfile(
        smallest_viable_version=(
            impl.get("smallest_viable_version")
            or legacy.get("smallest_viable_version")
        ),
        tools=tools,
        materials=materials,
        expected_time=expected_time,
        expected_cost=expected_cost,
        success_checks=success_checks,
        stop_conditions=stop_conditions,
        common_mistakes=common_mistakes,
        variants=variants,
        when_to_escalate=when_to_escalate,
    )

    if not any([
        profile.smallest_viable_version,
        profile.tools,
        profile.materials,
        profile.expected_time,
        profile.success_checks,
        profile.stop_conditions,
        profile.common_mistakes,
        profile.variants,
        profile.when_to_escalate,
    ]):
        return None
    return profile


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
