from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum as SQLAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from capability_commons.db.base import Base
from capability_commons.domain.enums import (
    COType,
    ContradictionDimension,
    ContradictionStatus,
    CostBand,
    EdgeType,
    EntityStatus,
    EntityType,
    EvidenceSourceKind,
    FacetType,
    LifecycleState,
    NodeKind,
    ProvenanceMethod,
    ReadingLevel,
    RelationStatus,
    RetrievalIntent,
    RetrievalRunStatus,
    RetrievalStepType,
    ReviewOutcome,
    ReviewType,
    RiskBand,
    SeverityLevel,
    StageType,
    TrustTier,
    ValidityStatus,
    VisibilityType,
    WorkspaceVisibility,
)


def _enum(enum_cls: type, name: str) -> SQLAEnum:
    return SQLAEnum(enum_cls, name=name, values_callable=lambda e: [member.value for member in e])


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[WorkspaceVisibility] = mapped_column(_enum(WorkspaceVisibility, "workspace_visibility"), nullable=False, default=WorkspaceVisibility.PUBLIC)
    default_language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    context_objects: Mapped[list[ContextObject]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    entities: Mapped[list[Entity]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    evidence_sources: Mapped[list[EvidenceSource]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    retrieval_runs: Mapped[list[RetrievalRun]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class ContextObject(Base):
    __tablename__ = "context_objects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_context_objects_workspace_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[COType] = mapped_column(_enum(COType, "co_type"), nullable=False)
    canonical_title: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id"), nullable=True)
    lifecycle_state: Mapped[LifecycleState] = mapped_column(_enum(LifecycleState, "lifecycle_state"), nullable=False, default=LifecycleState.DRAFT)
    visibility: Mapped[VisibilityType] = mapped_column(_enum(VisibilityType, "visibility_type"), nullable=False, default=VisibilityType.PUBLIC)
    default_language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), server_onupdate=text("now()"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="context_objects", lazy="selectin")
    versions: Mapped[list[ContextObjectVersion]] = relationship(
        back_populates="context_object",
        cascade="all, delete-orphan",
        foreign_keys="ContextObjectVersion.context_object_id",
        order_by="ContextObjectVersion.version_no.desc()",
        lazy="selectin",
    )
    current_version: Mapped[ContextObjectVersion | None] = relationship(
        foreign_keys=[current_version_id],
        post_update=True,
        lazy="joined",
    )


class ContextObjectVersion(Base):
    __tablename__ = "context_object_versions"
    __table_args__ = (
        UniqueConstraint("context_object_id", "version_no", name="uq_cov_context_object_version_no"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        CheckConstraint("estimated_minutes > 0", name="estimated_minutes_positive"),
        CheckConstraint("source_confidence >= 0 AND source_confidence <= 1", name="source_confidence_range"),
        CheckConstraint("evidence_confidence >= 0 AND evidence_confidence <= 1", name="evidence_confidence_range"),
        Index("idx_cov_context_object_id", "context_object_id", "version_no"),
        Index("idx_cov_validity", "validity_status", "created_at"),
        Index("idx_cov_search_tsv", "search_tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    context_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_objects.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_medium: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_language: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_body: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    validity_status: Mapped[ValidityStatus] = mapped_column(_enum(ValidityStatus, "validity_status"), nullable=False, default=ValidityStatus.CURRENT)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage: Mapped[StageType | None] = mapped_column(_enum(StageType, "stage_type"), nullable=True)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_band: Mapped[CostBand] = mapped_column(_enum(CostBand, "cost_band"), nullable=False, default=CostBand.FREE)
    risk_band: Mapped[RiskBand] = mapped_column(_enum(RiskBand, "risk_band"), nullable=False, default=RiskBand.LOW)
    reading_level: Mapped[ReadingLevel] = mapped_column(_enum(ReadingLevel, "reading_level"), nullable=False, default=ReadingLevel.GENERAL)
    beginner_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    teach_forward_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_professional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    evidence_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    locale_scope: Mapped[str] = mapped_column(Text, nullable=False, default="global")
    language_code: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    supersedes_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id"), nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            """
            to_tsvector(
              'english',
              coalesce(title, '') || ' ' ||
              coalesce(summary_short, '') || ' ' ||
              coalesce(summary_medium, '') || ' ' ||
              coalesce(plain_language, '') || ' ' ||
              coalesce(markdown_body, '')
            )
            """,
            persisted=True,
        ),
        nullable=True,
    )

    context_object: Mapped[ContextObject] = relationship(back_populates="versions", foreign_keys=[context_object_id], lazy="joined")
    supersedes_version: Mapped[ContextObjectVersion | None] = relationship(remote_side="ContextObjectVersion.id")
    facets: Mapped[list[ContextObjectFacet]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    entities: Mapped[list[ContextObjectEntity]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    review_records: Mapped[list[ReviewRecord]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    object_files: Mapped[list[ObjectFile]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    segments: Mapped[list[ContentSegment]] = relationship(back_populates="version", cascade="all, delete-orphan", lazy="selectin")
    evidence_spans: Mapped[list[EvidenceSpan]] = relationship(back_populates="version", lazy="selectin")


class ContextObjectFacet(Base):
    __tablename__ = "context_object_facets"
    __table_args__ = (
        PrimaryKeyConstraint("context_object_version_id", "facet_type", "facet_value", name="pk_context_object_facets"),
        Index("idx_cof_facet_lookup", "facet_type", "facet_value", "context_object_version_id"),
    )

    context_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    facet_type: Mapped[FacetType] = mapped_column(_enum(FacetType, "facet_type"), nullable=False)
    facet_value: Mapped[str] = mapped_column(Text, nullable=False)

    version: Mapped[ContextObjectVersion] = relationship(back_populates="facets", lazy="joined")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("workspace_id", "entity_type", "canonical_name", name="uq_entities_workspace_type_name"),
        Index("idx_entities_lookup", "workspace_id", "entity_type", "canonical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(_enum(EntityType, "entity_type"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EntityStatus] = mapped_column(_enum(EntityStatus, "entity_status"), nullable=False, default=EntityStatus.ACTIVE)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    workspace: Mapped[Workspace] = relationship(back_populates="entities", lazy="selectin")
    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan", lazy="selectin")
    object_links: Mapped[list[ContextObjectEntity]] = relationship(back_populates="entity", cascade="all, delete-orphan", lazy="selectin")


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "alias", name="uq_entity_aliases_entity_alias"),
        Index("idx_entity_alias_lookup", "alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)

    entity: Mapped[Entity] = relationship(back_populates="aliases")


class ContextObjectEntity(Base):
    __tablename__ = "context_object_entities"
    __table_args__ = (PrimaryKeyConstraint("context_object_version_id", "entity_id", name="pk_context_object_entities"),)

    context_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    role_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    version: Mapped[ContextObjectVersion] = relationship(back_populates="entities", lazy="joined")
    entity: Mapped[Entity] = relationship(back_populates="object_links", lazy="joined")


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (
        Index("idx_edges_src", "workspace_id", "src_node_kind", "src_id", "edge_type"),
        Index("idx_edges_dst", "workspace_id", "dst_node_kind", "dst_id", "edge_type"),
        Index("idx_edges_status", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    src_node_kind: Mapped[NodeKind] = mapped_column(_enum(NodeKind, "node_kind"), nullable=False)
    src_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    edge_type: Mapped[EdgeType] = mapped_column(_enum(EdgeType, "edge_type"), nullable=False)
    dst_node_kind: Mapped[NodeKind] = mapped_column(_enum(NodeKind, "node_kind"), nullable=False)
    dst_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("1.0"))
    provenance_method: Mapped[ProvenanceMethod] = mapped_column(_enum(ProvenanceMethod, "provenance_method"), nullable=False, default=ProvenanceMethod.HUMAN_AUTHORED)
    status: Mapped[RelationStatus] = mapped_column(_enum(RelationStatus, "relation_status"), nullable=False, default=RelationStatus.CURRENT)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    evidence_links: Mapped[list[EdgeEvidenceSpan]] = relationship(back_populates="edge", cascade="all, delete-orphan")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    source_kind: Mapped[EvidenceSourceKind] = mapped_column(_enum(EvidenceSourceKind, "evidence_source_kind"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_tier: Mapped[TrustTier] = mapped_column(_enum(TrustTier, "trust_tier"), nullable=False, default=TrustTier.SECONDARY)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_code: Mapped[str] = mapped_column(Text, nullable=False, default="en")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    workspace: Mapped[Workspace] = relationship(back_populates="evidence_sources", lazy="selectin")
    spans: Mapped[list[EvidenceSpan]] = relationship(back_populates="source", cascade="all, delete-orphan", lazy="selectin")


class EvidenceSpan(Base):
    __tablename__ = "evidence_spans"
    __table_args__ = (
        CheckConstraint("start_char >= 0", name="start_char_non_negative"),
        CheckConstraint("end_char >= start_char", name="end_char_ge_start_char"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="CASCADE"), nullable=False)
    context_object_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="SET NULL"), nullable=True)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_segments.id", ondelete="SET NULL"), nullable=True)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    source: Mapped[EvidenceSource] = relationship(back_populates="spans", lazy="joined")
    version: Mapped[ContextObjectVersion | None] = relationship(back_populates="evidence_spans", lazy="joined")
    segment: Mapped[ContentSegment | None] = relationship(back_populates="evidence_spans", lazy="joined")
    edge_links: Mapped[list[EdgeEvidenceSpan]] = relationship(back_populates="evidence_span", cascade="all, delete-orphan", lazy="selectin")


class EdgeEvidenceSpan(Base):
    __tablename__ = "edge_evidence_spans"
    __table_args__ = (PrimaryKeyConstraint("edge_id", "evidence_span_id", name="pk_edge_evidence_spans"),)

    edge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("edges.id", ondelete="CASCADE"), nullable=False)
    evidence_span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence_spans.id", ondelete="CASCADE"), nullable=False)

    edge: Mapped[Edge] = relationship(back_populates="evidence_links")
    evidence_span: Mapped[EvidenceSpan] = relationship(back_populates="edge_links")


class ReviewRecord(Base):
    __tablename__ = "review_records"
    __table_args__ = (Index("idx_review_records_version", "context_object_version_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    context_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    review_type: Mapped[ReviewType] = mapped_column(_enum(ReviewType, "review_type"), nullable=False)
    outcome: Mapped[ReviewOutcome] = mapped_column(_enum(ReviewOutcome, "review_outcome"), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    version: Mapped[ContextObjectVersion] = relationship(back_populates="review_records", lazy="joined")


class ContradictionCase(Base):
    __tablename__ = "contradiction_cases"
    __table_args__ = (Index("idx_contradiction_cases_versions", "left_version_id", "right_version_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    left_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    right_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    dimension: Mapped[ContradictionDimension] = mapped_column(_enum(ContradictionDimension, "contradiction_dimension"), nullable=False)
    severity: Mapped[SeverityLevel] = mapped_column(_enum(SeverityLevel, "severity_level"), nullable=False, default=SeverityLevel.MEDIUM)
    status: Mapped[ContradictionStatus] = mapped_column(_enum(ContradictionStatus, "contradiction_status"), nullable=False, default=ContradictionStatus.OPEN)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="SET NULL"), nullable=True)


class ContentSegment(Base):
    __tablename__ = "content_segments"
    __table_args__ = (
        UniqueConstraint("context_object_version_id", "ordinal", name="uq_content_segments_version_ordinal"),
        CheckConstraint("token_count IS NULL OR token_count >= 0", name="token_count_non_negative"),
        Index("idx_content_segments_version", "context_object_version_id", "ordinal"),
        Index(
            "idx_content_segments_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    context_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    version: Mapped[ContextObjectVersion] = relationship(back_populates="segments", lazy="joined")
    evidence_spans: Mapped[list[EvidenceSpan]] = relationship(back_populates="segment")


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"
    __table_args__ = (Index("idx_retrieval_runs_workspace_created_at", "workspace_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    requester_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    intent: Mapped[RetrievalIntent] = mapped_column(_enum(RetrievalIntent, "retrieval_intent"), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    task_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    compiled_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[RetrievalRunStatus] = mapped_column(_enum(RetrievalRunStatus, "retrieval_run_status"), nullable=False, default=RetrievalRunStatus.RUNNING)
    sufficiency_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("0.0"))
    budget_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    result_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="retrieval_runs")
    steps: Mapped[list[RetrievalStep]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RetrievalStep(Base):
    __tablename__ = "retrieval_steps"
    __table_args__ = (
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="latency_ms_non_negative"),
        Index("idx_retrieval_steps_run_iteration", "retrieval_run_id", "iteration_no", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("retrieval_runs.id", ondelete="CASCADE"), nullable=False)
    iteration_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[RetrievalStepType] = mapped_column(_enum(RetrievalStepType, "retrieval_step_type"), nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_spent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    run: Mapped[RetrievalRun] = relationship(back_populates="steps")


class ObjectFile(Base):
    __tablename__ = "object_files"
    __table_args__ = (CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="byte_size_non_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    context_object_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False)
    object_store_key: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    version: Mapped[ContextObjectVersion] = relationship(back_populates="object_files")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("idx_outbox_unprocessed", "processed_at", postgresql_where=text("processed_at IS NULL")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_key_hash", "key_hash", unique=True),
        Index("idx_api_keys_workspace", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(lazy="selectin")


class RateLimitLog(Base):
    __tablename__ = "rate_limit_log"
    __table_args__ = (
        UniqueConstraint("key_hash", "window_start", name="uq_rate_limit_key_window"),
        Index("idx_rate_limit_log_window", "window_start"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # No FK to api_keys.key_hash: avoids lock contention on high-write table
    # and allows rate-limit records to persist after key revocation/deletion.
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
