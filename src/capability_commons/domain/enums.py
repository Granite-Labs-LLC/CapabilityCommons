from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class WorkspaceVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class COType(StrEnum):
    CONCEPT_NOTE = "concept_note"
    SKILL_GUIDE = "skill_guide"
    PROJECT_BLUEPRINT = "project_blueprint"
    MODULE = "module"
    ASSESSMENT = "assessment"
    WORKSHEET = "worksheet"
    REFERENCE_SHEET = "reference_sheet"
    GLOSSARY = "glossary"
    TEACH_FORWARD_PACKET = "teach_forward_packet"
    LEARNING_PATH = "learning_path"
    FIELD_REPORT = "field_report"
    LOCAL_ADAPTATION = "local_adaptation"
    EXPERT_REVIEW = "expert_review"
    CORRECTION = "correction"
    SAFETY_NOTICE = "safety_notice"
    TRANSLATION = "translation"
    COMMUNITY_MAP = "community_map"
    RESOURCE_DIRECTORY = "resource_directory"


class LifecycleState(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    VERIFIED = "verified"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ValidityStatus(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    DEPRECATED = "deprecated"
    RETRACTED = "retracted"


class VisibilityType(StrEnum):
    PUBLIC = "public"
    CONTRIBUTOR_ONLY = "contributor_only"
    EDITORIAL = "editorial"
    RESTRICTED = "restricted"


class StageType(StrEnum):
    FOUNDATION = "foundation"
    HOUSEHOLD = "household"
    PRODUCTIVE = "productive"
    COMMUNITY = "community"
    ADVANCED = "advanced"


class CostBand(StrEnum):
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskBand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXPERT_ONLY = "expert_only"


class ReadingLevel(StrEnum):
    GENERAL = "general"
    INTERMEDIATE = "intermediate"
    TECHNICAL = "technical"


class FacetType(StrEnum):
    DOMAIN = "domain"
    AUDIENCE = "audience"
    HOUSING_TYPE = "housing_type"
    SETTLEMENT_TYPE = "settlement_type"
    BUDGET_PROFILE = "budget_profile"
    CLIMATE_ZONE = "climate_zone"
    UTILITY_PROFILE = "utility_profile"
    LOCALE = "locale"
    LANGUAGE = "language"
    DELIVERY_MODE = "delivery_mode"


class EntityType(StrEnum):
    TOPIC = "topic"
    TOOL = "tool"
    MATERIAL = "material"
    HAZARD = "hazard"
    STANDARD = "standard"
    REGULATION = "regulation"
    ORGANIZATION = "organization"
    PERSON = "person"
    PLACE = "place"
    CLIMATE_ZONE = "climate_zone"
    HOUSING_TYPE = "housing_type"
    LEARNER_PROFILE = "learner_profile"
    COMMUNITY_ASSET = "community_asset"


class EntityStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MERGED = "merged"


class NodeKind(StrEnum):
    OBJECT_VERSION = "object_version"
    ENTITY = "entity"


class EdgeType(StrEnum):
    CONTAINS = "contains"
    PREREQUISITE_FOR = "prerequisite_for"
    BUILDS_ON = "builds_on"
    ASSESSED_BY = "assessed_by"
    NEXT_STEP_FOR = "next_step_for"
    ALTERNATIVE_TO = "alternative_to"
    SUPPORTED_BY = "supported_by"
    DERIVED_FROM = "derived_from"
    QUOTES = "quotes"
    SUMMARIZES = "summarizes"
    VALIDATED_BY = "validated_by"
    CONTRADICTED_BY = "contradicted_by"
    SUPERSEDES = "supersedes"
    DEPRECATED_BY = "deprecated_by"
    CORRECTED_BY = "corrected_by"
    TRANSLATED_FROM = "translated_from"
    FORKED_FROM = "forked_from"
    ADAPTED_FOR = "adapted_for"
    APPLIES_IN = "applies_in"
    REQUIRES_TOOL = "requires_tool"
    REQUIRES_MATERIAL = "requires_material"
    HAS_FAILURE_MODE = "has_failure_mode"
    MITIGATED_BY = "mitigated_by"
    UNSAFE_WITHOUT = "unsafe_without"
    BOUNDED_BY = "bounded_by"


class ProvenanceMethod(StrEnum):
    HUMAN_AUTHORED = "human_authored"
    DETERMINISTIC_RULE = "deterministic_rule"
    LLM_EXTRACTED = "llm_extracted"
    IMPORTED = "imported"
    HUMAN_VERIFIED = "human_verified"


class RelationStatus(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"
    DEPRECATED = "deprecated"


class EvidenceSourceKind(StrEnum):
    URL = "url"
    FILE = "file"
    BOOK = "book"
    STANDARD = "standard"
    FIELD_OBSERVATION = "field_observation"
    TRANSCRIPT = "transcript"
    PHOTO = "photo"
    MEASUREMENT = "measurement"
    EXTERNAL_DOC = "external_doc"


class TrustTier(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FIELD_NOTE = "field_note"
    ANECDOTAL = "anecdotal"


class ReviewType(StrEnum):
    EDITORIAL = "editorial"
    EXPERT = "expert"
    PEDAGOGY = "pedagogy"
    SAFETY = "safety"
    TRANSLATION = "translation"
    FACT_CHECK = "fact_check"


class ReviewOutcome(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"
    DISPUTED = "disputed"


class ContradictionDimension(StrEnum):
    FACTUAL = "factual"
    SAFETY = "safety"
    CURRENCY = "currency"
    REGIONAL = "regional"
    TERMINOLOGY = "terminology"
    SCOPE = "scope"


class SeverityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContradictionStatus(StrEnum):
    OPEN = "open"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    ACCEPTED_CONTEXTUAL = "accepted_contextual"
    REJECTED = "rejected"


class RetrievalIntent(StrEnum):
    HOW_TO = "how_to"
    LEARN_PATH = "learn_path"
    WHY = "why"
    COMPARE_OPTIONS = "compare_options"
    LOCALIZE = "localize"
    DEBUG_FAILURE = "debug_failure"
    TEACH_FORWARD = "teach_forward"
    WHAT_CHANGED = "what_changed"
    SAFETY_CHECK = "safety_check"


class RetrievalRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


class RetrievalStepType(StrEnum):
    RESOLVE_SEEDS = "resolve_seeds"
    SEARCH = "search"
    GRAPH_EXPAND = "graph_expand"
    RERANK = "rerank"
    SUFFICIENCY = "sufficiency"
    ASSEMBLE = "assemble"


class AssessmentType(StrEnum):
    QUIZ = "quiz"
    CHECKLIST = "checklist"
    DEMO = "demo"
    PORTFOLIO_REVIEW = "portfolio_review"
