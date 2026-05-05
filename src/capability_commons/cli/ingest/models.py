"""Pydantic models for ingestion pipeline intermediate artifacts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# --- Pass 0: Segments ---

class SourceSegment(BaseModel):
    """A page-preserving text segment extracted from a source document."""
    source_id: str
    segment_id: str
    page_start: int
    page_end: int
    heading_path: list[str]
    text: str
    start_char: int
    end_char: int
    figure_refs: list[str] = []
    table_refs: list[str] = []


# --- Pass 1: Extraction Matrix ---

class ExtractionRow(BaseModel):
    """A candidate capability object identified from source material."""
    source_id: str
    section_id: str
    start_page: int
    end_page: int
    heading_path: str
    segment_ids: list[str]
    candidate_slug: str
    candidate_type: Literal[
        "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
        "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
        "field_report", "worksheet", "glossary", "safety_notice", "correction",
    ]
    primary_domain: str
    secondary_domains: list[str] = []
    stage: str
    contexts: list[str] = []
    summary: str
    key_concepts: list[str] = []
    key_actions: list[str] = []
    tools_materials: list[str] = []
    failure_modes: list[str] = []
    safety_boundaries: list[str] = []
    local_adaptation_signals: list[str] = []
    needs_split: bool = False
    needs_merge: bool = False
    confidence: float


# --- Pass 3: Citations ---

class CitationSpan(BaseModel):
    """A link from a claim to a source text span."""
    source_id: str
    page_start: int
    page_end: int
    segment_id: str
    excerpt: str
    start_char: int
    end_char: int
    support_strength: Literal["strong", "medium", "weak"]


class ClaimCitation(BaseModel):
    """A drafted claim linked to supporting source spans."""
    object_id: str
    claim_id: str
    claim_text: str
    support: list[CitationSpan]


# --- Pass 4: Canonicalization ---

class CanonicalizationDecision(BaseModel):
    """A merge/split/keep decision for a group of similar drafts."""
    action: Literal["keep", "merge", "split"]
    rationale: str
    canonical_slug: str
    deprecated_draft_ids: list[str] = []
    merged_object: dict | None = None
    split_objects: list[dict] = []


# --- Pass 5: Edges ---

class ExtractedEdge(BaseModel):
    """A typed directed edge between two knowledge objects."""
    source_id: str
    target_id: str
    edge_type: str
    sequence: int | None = None
    condition: str | None = None
    confidence: float


# --- Pass 6: Bundles ---

class BundleOutput(BaseModel):
    """Six-part public bundle for a knowledge object."""
    hook: str
    primer: str
    guide: str
    reference: list[str]
    worksheet: list[str]
    teach_forward_kit: dict[str, str | list[str]]


# --- Validation ---

class ValidationReport(BaseModel):
    """Summary report from the validate command."""
    objects_count: int
    edges_count: int
    citations_count: int
    errors: list[str]
    warnings: list[str]
    citation_coverage: float
    # PLAN P1-8: separate gate for publish-readiness. When `strict=True`,
    # additional checks run (≥2 citations per actionable object, presence of
    # the implementation envelope, etc.) and any violation lands in `errors`.
    publish_blockers: list[str] = []


# --- Project Manifest ---

class PassStatus(BaseModel):
    """Completion status for a single pipeline pass."""
    completed: datetime | None = None


class PassesStatus(BaseModel):
    """Completion status for all pipeline passes."""
    parse: PassStatus = PassStatus()
    extract: PassStatus = PassStatus()
    draft: PassStatus = PassStatus()
    cite: PassStatus = PassStatus()
    canonicalize: PassStatus = PassStatus()
    edges: PassStatus = PassStatus()
    bundles: PassStatus = PassStatus()
    load: PassStatus = PassStatus()


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.2


class ManifestSource(BaseModel):
    """A source document registered in the project."""
    id: str
    file: str
    title: str
    source_kind: str


class ProjectManifest(BaseModel):
    """Top-level manifest for an ingestion project."""
    name: str
    created: str
    sources: list[ManifestSource]
    llm: LLMConfig = LLMConfig()
    passes: PassesStatus = PassesStatus()
    # PLAN P1-7: when set, every mark_pass_complete also mirrors progress
    # into the IngestJob/IngestJobPass tables so contributors and reviewers
    # can see live state via /v1/ingest/jobs/{id}. Filesystem stays the
    # canonical workflow medium for the operator; the DB is the export.
    job_id: str | None = None
