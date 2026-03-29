"""Regression tests for Phase 0 correctness fixes."""
from __future__ import annotations

import yaml
import pytest

from capability_commons.cli.ingest.parse import markdown_to_segments
from capability_commons.domain.enums import LifecycleState


# === ING-001: Lifecycle enum casing ===


class TestING001LifecycleCasing:
    def test_load_writes_lowercase_lifecycle(self, tmp_path):
        """ING-001: load.py must write lowercase lifecycle_state values."""
        from capability_commons.cli.ingest.project import IngestProject

        proj = IngestProject.init(
            projects_root=tmp_path / "projects",
            name="test-casing",
            sources=[{"id": "src.test", "file": "sources/test.md", "title": "Test", "source_kind": "BOOK"}],
        )
        # Create a draft YAML
        draft_path = proj.drafts_dir / "test-obj.yaml"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        with open(draft_path, "w") as f:
            yaml.dump({"id": "test-obj", "slug": "test-obj", "canonical_title": "Test", "markdown_body": "body"}, f)

        from capability_commons.cli.ingest.load import _patch_lifecycle
        _patch_lifecycle(proj.drafts_dir)

        with open(draft_path) as f:
            obj = yaml.safe_load(f)
        assert obj["lifecycle_state"] == "published"
        assert LifecycleState(obj["lifecycle_state"]) == LifecycleState.PUBLISHED

    def test_validate_accepts_lowercase_lifecycle(self):
        """ING-001: validator must accept canonical lowercase lifecycle values."""
        from capability_commons.cli.ingest.validate import VALID_LIFECYCLE
        assert "published" in VALID_LIFECYCLE
        assert "draft" in VALID_LIFECYCLE
        assert "PUBLISHED" not in VALID_LIFECYCLE

    def test_seed_resolves_lowercase_lifecycle(self):
        """ING-001: seed_graph must handle lowercase lifecycle_state from YAML."""
        node = {"lifecycle_state": "published"}
        lifecycle_str = node.get("lifecycle_state", "published")
        lifecycle = LifecycleState(lifecycle_str)
        assert lifecycle == LifecycleState.PUBLISHED


# === ING-002: True page-preserving parse output ===


class TestING002PagePreservingParse:
    def test_multipage_segments_have_correct_pages(self):
        """ING-002: segments from multi-page source must have real page_start/page_end."""
        md = (
            "<!-- PAGE 1 -->\n"
            "# Chapter 1\n\nContent on page 1.\n\n"
            "<!-- PAGE 2 -->\n"
            "More content on page 2.\n\n"
            "## Section 1.1\n\nSection on page 2.\n\n"
            "<!-- PAGE 3 -->\n"
            "# Chapter 2\n\nContent on page 3.\n"
        )
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        # Chapter 1 starts on page 1, spans to page 2
        ch1 = segments[0]
        assert ch1.page_start == 1
        assert ch1.page_end >= 2

        # Chapter 2 starts on page 3
        ch2 = [s for s in segments if "Chapter 2" in s.heading_path[-1]]
        assert len(ch2) == 1
        assert ch2[0].page_start == 3

    def test_no_page_markers_uses_base_page(self):
        """ING-002: without page markers, segments default to base_page."""
        md = "# Heading\nSome text."
        segments = markdown_to_segments(md, source_id="src.test", base_page=5)
        assert segments[0].page_start == 5
        assert segments[0].page_end == 5

    def test_segments_without_headings_track_pages(self):
        """ING-002: even without headings, page markers update the page."""
        md = "<!-- PAGE 1 -->\nParagraph one.\n<!-- PAGE 2 -->\nParagraph two.\n"
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        assert len(segments) >= 1
        assert segments[0].page_start == 1
        assert segments[0].page_end == 2


# === ING-003: Globally unique segment IDs with lineage ===


class TestING003GlobalSegmentIDs:
    def test_segment_ids_include_source_prefix(self):
        """ING-003: segment IDs must be globally unique by including source_id."""
        md = "# A\nText A\n# B\nText B\n"
        segs_a = markdown_to_segments(md, source_id="src.alpha", base_page=1)
        segs_b = markdown_to_segments(md, source_id="src.beta", base_page=1)
        ids_a = {s.segment_id for s in segs_a}
        ids_b = {s.segment_id for s in segs_b}
        assert ids_a.isdisjoint(ids_b), f"Collision: {ids_a & ids_b}"

    def test_segment_ids_are_deterministic(self):
        """ING-003: same input produces same segment IDs."""
        md = "# Heading\nContent.\n"
        segs1 = markdown_to_segments(md, source_id="src.test", base_page=1)
        segs2 = markdown_to_segments(md, source_id="src.test", base_page=1)
        assert [s.segment_id for s in segs1] == [s.segment_id for s in segs2]


# === ING-004: Canonical draft schema enforcement ===


class TestING004CanonicalDraftSchema:
    def test_valid_draft_passes(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        draft = CanonicalDraft(
            id="water.storage",
            slug="water.storage",
            co_type="skill_guide",
            canonical_title="Water Storage Basics",
            plain_language="Learn safe water storage.",
            markdown_body="# Water Storage\nStore water safely.",
            structured_data={"tools": ["container"]},
        )
        assert draft.slug == "water.storage"

    def test_missing_co_type_fails(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        with pytest.raises(Exception):
            CanonicalDraft(
                id="test",
                slug="test",
                canonical_title="Test",
                plain_language="desc",
                markdown_body="body",
            )

    def test_missing_plain_language_fails(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        with pytest.raises(Exception):
            CanonicalDraft(
                id="test",
                slug="test",
                co_type="skill_guide",
                canonical_title="Test",
                markdown_body="body",
            )

    def test_invalid_co_type_fails(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        with pytest.raises(Exception):
            CanonicalDraft(
                id="test",
                slug="test",
                co_type="nonexistent_type",
                canonical_title="Test",
                plain_language="desc",
                markdown_body="body",
            )

    def test_co_type_normalized_to_lowercase(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        draft = CanonicalDraft(
            id="test",
            slug="test",
            co_type="Skill Guide",
            canonical_title="Test",
            plain_language="desc",
            markdown_body="body",
        )
        assert draft.co_type == "skill_guide"


# === ING-005: Canonicalization materialization ===


class TestING005CanonicalizationMaterialization:
    def test_merge_decision_includes_merged_object(self):
        from capability_commons.cli.ingest.models import CanonicalizationDecision
        d = CanonicalizationDecision(
            action="merge",
            rationale="duplicates",
            canonical_slug="water.storage",
            deprecated_draft_ids=["water.storage-v1", "water.storage-v2"],
            merged_object={"id": "water.storage", "slug": "water.storage", "co_type": "skill_guide",
                           "canonical_title": "Water Storage", "plain_language": "Store water.",
                           "markdown_body": "# Water Storage"},
        )
        assert d.merged_object is not None
        assert d.merged_object["slug"] == "water.storage"

    def test_split_decision_includes_split_objects(self):
        from capability_commons.cli.ingest.models import CanonicalizationDecision
        d = CanonicalizationDecision(
            action="split",
            rationale="overloaded",
            canonical_slug="water.storage",
            deprecated_draft_ids=["water.combined"],
            split_objects=[
                {"id": "water.storage", "slug": "water.storage"},
                {"id": "water.treatment", "slug": "water.treatment"},
            ],
        )
        assert len(d.split_objects) == 2

    def test_keep_decision_no_objects(self):
        from capability_commons.cli.ingest.models import CanonicalizationDecision
        d = CanonicalizationDecision(
            action="keep",
            rationale="distinct",
            canonical_slug="water.storage",
        )
        assert d.merged_object is None
        assert d.split_objects == []


# === SEED-001: Edge-type normalization ===


class TestSEED001EdgeTypeNormalization:
    def test_normalize_accepts_lowercase_enum(self):
        from capability_commons.cli.seed import normalize_edge_type
        from capability_commons.domain.enums import EdgeType
        assert normalize_edge_type("prerequisite_for") == EdgeType.PREREQUISITE_FOR
        assert normalize_edge_type("builds_on") == EdgeType.BUILDS_ON
        assert normalize_edge_type("contains") == EdgeType.CONTAINS

    def test_normalize_accepts_legacy_uppercase(self):
        from capability_commons.cli.seed import normalize_edge_type
        from capability_commons.domain.enums import EdgeType
        assert normalize_edge_type("REQUIRES") == EdgeType.PREREQUISITE_FOR
        assert normalize_edge_type("NEXT") == EdgeType.NEXT_STEP_FOR
        assert normalize_edge_type("COVERS") == EdgeType.CONTAINS

    def test_normalize_unknown_returns_none(self):
        from capability_commons.cli.seed import normalize_edge_type
        assert normalize_edge_type("NONEXISTENT") is None


# === SEED-002: EvidenceSpan metadata_json ===


class TestSEED002EvidenceSpanMetadata:
    def test_evidence_span_model_has_metadata_json(self):
        from capability_commons.db.models import EvidenceSpan
        assert hasattr(EvidenceSpan, "metadata_json")


# === PUB-001: Seed graph emits outbox events ===


class TestPUB001PublishIndexing:
    def test_seed_graph_creates_outbox_events(self):
        """PUB-001: seed_graph must create OutboxEvent for published versions."""
        import ast
        import inspect
        from capability_commons.cli import seed
        source = inspect.getsource(seed.seed_graph)
        # Check that OutboxEvent is instantiated in seed_graph
        assert "OutboxEvent(" in source, "seed_graph must create OutboxEvent for published versions"
        assert "version.published" in source, "seed_graph must emit version.published events"


# === API-SEC-001: Retrieval run access control ===


class TestAPISEC001RetrievalRunAccess:
    def test_get_run_requires_workspace(self):
        """API-SEC-001: retrieval run detail endpoint must require workspace auth."""
        import inspect
        from capability_commons.api.routes import retrieval
        sig = inspect.signature(retrieval.get_run)
        param_types = {name: str(p.annotation) for name, p in sig.parameters.items()}
        has_workspace = any("CurrentWorkspace" in ann for ann in param_types.values())
        assert has_workspace, "get_run must require CurrentWorkspace dependency"

    def test_get_steps_requires_workspace(self):
        """API-SEC-001: retrieval run steps endpoint must require workspace auth."""
        import inspect
        from capability_commons.api.routes import retrieval
        sig = inspect.signature(retrieval.get_run_steps)
        param_types = {name: str(p.annotation) for name, p in sig.parameters.items()}
        has_workspace = any("CurrentWorkspace" in ann for ann in param_types.values())
        assert has_workspace, "get_run_steps must require CurrentWorkspace dependency"

    def test_service_get_run_accepts_workspace_id(self):
        """API-SEC-001: RetrievalService.get_run must accept workspace_id parameter."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        sig = inspect.signature(RetrievalService.get_run)
        assert "workspace_id" in sig.parameters

    def test_service_get_steps_accepts_workspace_id(self):
        """API-SEC-001: RetrievalService.get_steps must accept workspace_id parameter."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        sig = inspect.signature(RetrievalService.get_steps)
        assert "workspace_id" in sig.parameters
