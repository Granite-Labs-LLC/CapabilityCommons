from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from capability_commons.domain.enums import AssessmentType, COType, SeverityLevel


class ToolTier(BaseModel):
    """A tool or material with tier classification."""
    name: str
    tier: str = Field(description="essential, recommended, or nice_to_have")
    substitutes: list[str] = Field(default_factory=list)


class ImplementationProfile(BaseModel):
    """Cross-cutting implementation-readiness fields.

    Any object type can carry these fields to make it actionable.
    Stored as structured_data["implementation_profile"].
    """
    smallest_viable_version: str | None = Field(None, description="Minimum viable version someone can attempt")
    preflight_checks: list[str] = Field(default_factory=list, description="Checks before starting")
    tools_tiered: list[ToolTier] = Field(default_factory=list, description="Tools with tier classification")
    materials_tiered: list[ToolTier] = Field(default_factory=list, description="Materials with tier classification")
    estimated_time_hours: float | None = Field(None, ge=0, description="Estimated time in hours")
    estimated_cost_band: str | None = Field(None, description="free, low, medium, high")
    success_checks: list[str] = Field(default_factory=list, description="How to verify success")
    stop_conditions: list[str] = Field(default_factory=list, description="When to stop and reassess")
    common_mistakes: list[str] = Field(default_factory=list, description="Frequent errors to avoid")
    variants: list[str] = Field(default_factory=list, description="Alternative approaches")
    escalation_guidance: str | None = Field(None, description="When to seek professional help")


class TeachForwardPayload(BaseModel):
    three_minute_script: str
    ten_minute_outline: list[str]
    handout_points: list[str]


class SkillGuideStructuredData(BaseModel):
    performance_statement: str
    learning_objectives: list[str] = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    steps_summary: list[str] = Field(min_length=1)
    success_criteria: list[str] = Field(min_length=1)
    failure_modes: list[str] = Field(min_length=1)
    safety_boundary: str
    stop_conditions: list[str] = Field(default_factory=list)
    teach_forward: TeachForwardPayload


class ProjectBlueprintStructuredData(BaseModel):
    goal: str
    deliverables: list[str] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    time_box_hours: float = Field(gt=0)
    team_size: int = Field(ge=1)
    budget_notes: str
    variants: list[str] = Field(default_factory=list)


class DeliveryProfile(BaseModel):
    seminar_minutes: int = Field(ge=0)
    lab_minutes: int = Field(ge=0)
    field_task_minutes: int = Field(ge=0)
    teach_forward_minutes: int = Field(ge=0)


class ModuleStructuredData(BaseModel):
    week: int = Field(ge=1)
    node_refs: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(min_length=1)
    seminar_outline: list[str] = Field(min_length=1)
    lab: str
    field_task: str
    teach_forward_task: str
    deliverable_refs: list[str] = Field(default_factory=list)
    assessment_ref: str | None = None
    delivery_profile: DeliveryProfile | None = None
    completion_requirements: list[str] = Field(default_factory=list)


class AssessmentStructuredData(BaseModel):
    assessment_type: AssessmentType
    rubric: list[str] = Field(min_length=1)
    passing_threshold: str
    evidence_required: list[str] = Field(default_factory=list)


class TeachForwardPacketStructuredData(BaseModel):
    audience: str
    duration_minutes: int = Field(gt=0)
    facilitator_outline: list[str] = Field(min_length=1)
    visual_aids: list[str] = Field(default_factory=list)
    handout_points: list[str] = Field(min_length=1)
    discussion_prompts: list[str] = Field(default_factory=list)


class FieldReportStructuredData(BaseModel):
    setting: str
    inputs: list[str] = Field(default_factory=list)
    observations: list[str] = Field(min_length=1)
    outcome: str
    failures: list[str] = Field(default_factory=list)
    adaptations: list[str] = Field(default_factory=list)
    confidence_note: str


class LocalAdaptationStructuredData(BaseModel):
    adapted_for: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(min_length=1)
    changes_from_canonical: list[str] = Field(min_length=1)
    applicability_limits: list[str] = Field(min_length=1)
    evidence_note: str


class CorrectionStructuredData(BaseModel):
    corrects_claim: str
    reason: str
    replacement_guidance: str
    severity: SeverityLevel
    effective_from: datetime


class ReferenceSheetStructuredData(BaseModel):
    key_points: list[str] = Field(min_length=1)
    checklists: list[str] = Field(default_factory=list)
    formulas_or_rules: list[str] = Field(default_factory=list)
    glossary_terms: list[str] = Field(default_factory=list)


class LearningPathStructuredData(BaseModel):
    path_goal: str
    target_profiles: list[str] = Field(min_length=1)
    completion_artifacts: list[str] = Field(default_factory=list)


STRUCTURED_DATA_MODELS: dict[COType, type[BaseModel]] = {
    COType.SKILL_GUIDE: SkillGuideStructuredData,
    COType.PROJECT_BLUEPRINT: ProjectBlueprintStructuredData,
    COType.MODULE: ModuleStructuredData,
    COType.ASSESSMENT: AssessmentStructuredData,
    COType.TEACH_FORWARD_PACKET: TeachForwardPacketStructuredData,
    COType.FIELD_REPORT: FieldReportStructuredData,
    COType.LOCAL_ADAPTATION: LocalAdaptationStructuredData,
    COType.CORRECTION: CorrectionStructuredData,
    COType.REFERENCE_SHEET: ReferenceSheetStructuredData,
    COType.LEARNING_PATH: LearningPathStructuredData,
}


def validate_structured_data(object_type: COType, data: dict[str, Any]) -> dict[str, Any]:
    model_cls = STRUCTURED_DATA_MODELS.get(object_type)
    if model_cls is None:
        return data
    validated = model_cls.model_validate(data)
    return validated.model_dump(mode="json")


def extract_implementation_profile(data: dict[str, Any]) -> ImplementationProfile | None:
    """Extract and validate the implementation_profile from structured_data, if present."""
    raw = data.get("implementation_profile")
    if raw is None:
        return None
    return ImplementationProfile.model_validate(raw)


def validate_structured_data_or_raise(object_type: COType, data: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_structured_data(object_type, data)
    except ValidationError as exc:  # pragma: no cover - exact pydantic message not stable
        raise ValueError(exc.json()) from exc
