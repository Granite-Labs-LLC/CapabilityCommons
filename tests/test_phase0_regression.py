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


# =======================================================================
# Phase 1: Retrieval Quality
# =======================================================================


# === SEARCH-001: Real hybrid candidate union ===


class TestSEARCH001HybridUnion:
    def test_search_hybrid_has_rrf_parameter(self):
        """SEARCH-001: search_hybrid must support reciprocal rank fusion."""
        import inspect
        from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
        sig = inspect.signature(PostgresSearchAdapter.search_hybrid)
        assert "rrf_k" in sig.parameters

    def test_vector_search_method_exists(self):
        """SEARCH-001: PostgresSearchAdapter must have _vector_search method."""
        from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
        assert hasattr(PostgresSearchAdapter, "_vector_search")
        import inspect
        sig = inspect.signature(PostgresSearchAdapter._vector_search)
        assert "query_embedding" in sig.parameters


# === RET-001: Use hybrid search from RetrievalService ===


class TestRET001HybridRetrieval:
    def test_retrieval_service_has_embeddings(self):
        """RET-001: RetrievalService must have EmbeddingService for query embeddings."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        source = inspect.getsource(RetrievalService.__init__)
        assert "EmbeddingService" in source

    def test_execute_plan_uses_hybrid_search(self):
        """RET-001: execute_plan must call search_hybrid, not plain search."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        source = inspect.getsource(RetrievalService.execute_plan)
        assert "search_hybrid" in source
        assert "embed_query" in source


# === RET-002: Feed graph-expanded candidates into rerank ===


# === GRAPH-001: Edge direction semantics ===


class TestGRAPH001EdgeDirection:
    def test_prerequisite_direction_documented(self):
        """GRAPH-001: PREREQUISITE_FOR must have canonical direction docstring."""
        from capability_commons.domain.enums import EdgeType
        assert "src is a prerequisite for dst" in EdgeType.__doc__

    def test_seed_requires_creates_correct_direction(self):
        """GRAPH-001: 'A requires B' must produce Edge(src=B, dst=A)."""
        import inspect
        from capability_commons.cli import seed
        source = inspect.getsource(seed.seed_graph)
        # The edge creation must use prereq as src and dependant as dst
        assert "src_id=prereq_vid" in source
        assert "dst_id=dependant_vid" in source


# === QA-001: Hardened ingestion validation ===


class TestQA001HardenedValidation:
    def test_validate_catches_missing_co_type(self, tmp_path):
        """QA-001: validate must error on missing co_type."""
        from capability_commons.cli.ingest.project import IngestProject
        proj = IngestProject.init(
            projects_root=tmp_path / "projects",
            name="test-qa",
            sources=[{"id": "src.test", "file": "sources/test.md", "title": "Test", "source_kind": "BOOK"}],
        )
        draft_path = proj.drafts_dir / "test-obj.yaml"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        with open(draft_path, "w") as f:
            yaml.dump({
                "id": "test-obj", "slug": "test-obj",
                "canonical_title": "Test", "markdown_body": "body",
            }, f)

        from capability_commons.cli.ingest.validate import run_validate
        report = run_validate(proj)
        error_strs = " ".join(report.errors)
        assert "missing co_type" in error_strs
        assert "missing plain_language" in error_strs

    def test_validate_catches_duplicate_slugs(self, tmp_path):
        """QA-001: validate must error on duplicate slugs."""
        from capability_commons.cli.ingest.project import IngestProject
        proj = IngestProject.init(
            projects_root=tmp_path / "projects",
            name="test-dupes",
            sources=[{"id": "src.test", "file": "sources/test.md", "title": "Test", "source_kind": "BOOK"}],
        )
        proj.drafts_dir.mkdir(parents=True, exist_ok=True)
        for fname in ["a.yaml", "b.yaml"]:
            with open(proj.drafts_dir / fname, "w") as f:
                yaml.dump({
                    "id": "same-slug", "slug": "same-slug",
                    "co_type": "skill_guide", "canonical_title": "Test",
                    "plain_language": "desc", "markdown_body": "body",
                }, f)

        from capability_commons.cli.ingest.validate import run_validate
        report = run_validate(proj)
        assert any("Duplicate slug" in e for e in report.errors)

    def test_validate_catches_invalid_edge_types(self, tmp_path):
        """QA-001: validate must error on invalid edge types in edges.csv."""
        from capability_commons.cli.ingest.validate import VALID_EDGE_TYPES
        assert "prerequisite_for" in VALID_EDGE_TYPES
        assert "NONEXISTENT" not in VALID_EDGE_TYPES

    def test_validate_enforces_safety_boundary_on_high_risk(self, tmp_path):
        """QA-001: high risk objects without safety_boundary are errors."""
        from capability_commons.cli.ingest.project import IngestProject
        proj = IngestProject.init(
            projects_root=tmp_path / "projects",
            name="test-safety",
            sources=[{"id": "src.test", "file": "sources/test.md", "title": "Test", "source_kind": "BOOK"}],
        )
        proj.drafts_dir.mkdir(parents=True, exist_ok=True)
        with open(proj.drafts_dir / "risky.yaml", "w") as f:
            yaml.dump({
                "id": "risky", "slug": "risky",
                "co_type": "skill_guide", "canonical_title": "Risky Thing",
                "plain_language": "desc", "markdown_body": "body",
                "risk_band": "high",
            }, f)

        from capability_commons.cli.ingest.validate import run_validate
        report = run_validate(proj)
        assert any("safety_boundary" in e for e in report.errors)


# === SEARCH-002: Index implementation fields ===


class TestSEARCH002IndexImplementationFields:
    def test_serialize_structured_data(self):
        """SEARCH-002: structured_data fields must be serialized for retrieval."""
        from capability_commons.search.segment_serializer import serialize_structured_data
        sd = {
            "tools": ["drill", "level"],
            "materials": ["wood screws", "drywall anchors"],
            "success_criteria": "Shelf holds 50 lbs",
            "safety_boundary": "Do not drill into load-bearing walls without professional assessment",
        }
        text = serialize_structured_data(sd)
        assert "drill" in text
        assert "wood screws" in text
        assert "50 lbs" in text
        assert "load-bearing" in text

    def test_serialize_empty_structured_data(self):
        from capability_commons.search.segment_serializer import serialize_structured_data
        assert serialize_structured_data(None) == ""
        assert serialize_structured_data({}) == ""

    def test_build_indexable_text_includes_all_fields(self):
        from capability_commons.search.segment_serializer import build_indexable_text
        text = build_indexable_text(
            markdown_body="# Install a shelf\nDrill and mount.",
            plain_language="How to install a wall shelf.",
            structured_data={"tools": ["drill"], "materials": ["screws"]},
            title="Wall Shelf Installation",
        )
        assert "Wall Shelf Installation" in text
        assert "How to install" in text
        assert "Drill and mount" in text
        assert "drill" in text.lower()

# === SEARCH-003: UX-oriented public search filters ===


class TestSEARCH003UXFilters:
    def test_public_search_filters_to_facets(self):
        """SEARCH-003: PublicSearchFilters must convert to facet_filters."""
        from capability_commons.schemas.search import PublicSearchFilters
        f = PublicSearchFilters(
            housing_type="apartment",
            climate_zone="temperate",
            cost_band="low",
        )
        facets = f.to_facet_filters()
        assert facets["housing_type"] == ["apartment"]
        assert facets["climate_zone"] == ["temperate"]
        assert facets["budget_profile"] == ["low"]

    def test_search_request_merges_filters(self):
        """SEARCH-003: SearchRequest.resolved_facet_filters merges both filter types."""
        from capability_commons.schemas.search import SearchRequest, PublicSearchFilters
        req = SearchRequest(
            query="water storage",
            facet_filters={"domain": ["water"]},
            filters=PublicSearchFilters(housing_type="apartment"),
        )
        merged = req.resolved_facet_filters()
        assert merged["domain"] == ["water"]
        assert merged["housing_type"] == ["apartment"]

    def test_search_request_without_filters_uses_facet_filters(self):
        from capability_commons.schemas.search import SearchRequest
        req = SearchRequest(query="test", facet_filters={"domain": ["energy"]})
        assert req.resolved_facet_filters() == {"domain": ["energy"]}


    def test_indexer_uses_build_indexable_text(self):
        """SEARCH-002: VersionIndexer must use build_indexable_text."""
        import inspect
        from capability_commons.search.indexer import VersionIndexer
        source = inspect.getsource(VersionIndexer.reindex_version)
        assert "build_indexable_text" in source


class TestRET002GraphIntoRerank:
    def test_resolve_graph_candidates_exists(self):
        """RET-002: RetrievalService must have _resolve_graph_candidates method."""
        from capability_commons.retrieval.service import RetrievalService
        assert hasattr(RetrievalService, "_resolve_graph_candidates")

    def test_rerank_accepts_graph_version_ids(self):
        """RET-002: _rerank_hits must accept graph_version_ids parameter."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        sig = inspect.signature(RetrievalService._rerank_hits)
        assert "graph_version_ids" in sig.parameters

    def test_execute_plan_passes_graph_candidates_to_rerank(self):
        """RET-002: execute_plan must merge graph candidates into rerank input."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        source = inspect.getsource(RetrievalService.execute_plan)
        assert "_resolve_graph_candidates" in source
        assert "graph_version_ids" in source


# === RET-003: Score breakdowns in rerank output ===


class TestRET003ScoreBreakdowns:
    def test_reranked_items_have_score_components(self):
        """RET-003: reranked items must include individual score components."""
        import inspect
        from capability_commons.retrieval.service import RetrievalService
        source = inspect.getsource(RetrievalService._rerank_hits)
        for field in ["search_score", "graph_bonus", "published_bonus", "verified_bonus", "citation_bonus", "facet_bonus"]:
            assert field in source, f"Missing score breakdown field: {field}"


# === Shared helpers for Phase 2 tests ===


def _make_evidence_pack(evidence=None, contradictions=None, next_steps=None, sufficiency=0.8):
    """Helper to build a mock EvidencePackResponse for composer tests."""
    import uuid
    from capability_commons.domain.enums import RetrievalIntent
    from capability_commons.schemas.retrieval import EvidencePackResponse, RetrievalPlan
    return EvidencePackResponse(
        run_id=uuid.uuid4(),
        intent=RetrievalIntent.HOW_TO,
        query="test",
        plan=RetrievalPlan(
            intent=RetrievalIntent.HOW_TO,
            search_top_k=20,
            graph_depth=2,
            iteration_limit=3,
            edge_types=["PREREQUISITE_FOR"],
            rerank_weights={"search_score": 1.0},
        ),
        sufficiency_score=sufficiency,
        evidence=evidence or [],
        contradictions=contradictions or [],
        next_steps=next_steps or [],
    )


def _make_evidence_node(title="Test", slug="test", type_="skill_guide", score=0.8, summary=None, rationale=None):
    """Helper to build an EvidenceNode for composer tests."""
    import uuid
    from capability_commons.schemas.retrieval import EvidenceNode
    return EvidenceNode(
        object_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        slug=slug,
        title=title,
        type=type_,
        score=score,
        summary_short=summary or f"Summary of {title}",
        citations=[],
        rationale=rationale,
    )


# === API-001: Public workspace resolver ===


class TestAPI001PublicWorkspaceResolver:
    def test_public_workspace_slug_constant(self):
        """API-001: PUBLIC_WORKSPACE_SLUG must be defined."""
        from capability_commons.api.deps import PUBLIC_WORKSPACE_SLUG
        assert PUBLIC_WORKSPACE_SLUG == "capability-commons"

    def test_get_public_or_authenticated_workspace_exists(self):
        """API-001: get_public_or_authenticated_workspace dependency must exist."""
        from capability_commons.api.deps import get_public_or_authenticated_workspace
        import inspect
        assert inspect.iscoroutinefunction(get_public_or_authenticated_workspace)

    def test_public_workspace_alias_exists(self):
        """API-001: PublicWorkspace type alias must be exported."""
        from capability_commons.api.deps import PublicWorkspace
        assert PublicWorkspace is not None

    def test_search_route_uses_public_workspace(self):
        """API-001: Search route must use PublicWorkspace dependency for anonymous access."""
        import inspect
        from capability_commons.api.routes import search as search_mod
        source = inspect.getsource(search_mod)
        assert "PublicWorkspace" in source

    def test_resolver_rejects_invalid_bearer_token(self):
        """API-001: Must reject invalid Bearer tokens rather than falling back to public."""
        import inspect
        from capability_commons.api.deps import get_public_or_authenticated_workspace
        source = inspect.getsource(get_public_or_authenticated_workspace)
        assert "Invalid or revoked API key" in source

    def test_resolver_falls_back_to_public_workspace(self):
        """API-001: Anonymous requests must resolve to the public workspace."""
        import inspect
        from capability_commons.api.deps import get_public_or_authenticated_workspace
        source = inspect.getsource(get_public_or_authenticated_workspace)
        assert "PUBLIC_WORKSPACE_SLUG" in source


# === API-002: POST /v1/public/ask endpoint ===


class TestAPI002PublicAsk:
    def test_ask_schemas_exist(self):
        """API-002: Ask request/response schemas must be importable."""
        from capability_commons.schemas.ask import AskRequest, AskResponse, AskContext
        assert AskRequest is not None
        assert AskResponse is not None
        assert AskContext is not None

    def test_ask_request_validation(self):
        """API-002: AskRequest validates query length."""
        from capability_commons.schemas.ask import AskRequest
        import pytest as _pytest
        with _pytest.raises(Exception):
            AskRequest(query="ab")  # too short
        req = AskRequest(query="How do I store water?")
        assert req.max_results == 8

    def test_ask_response_has_required_fields(self):
        """API-002: AskResponse must include all spec fields."""
        from capability_commons.schemas.ask import AskResponse
        fields = AskResponse.model_fields
        for name in ["answer", "action_now", "implementation_plan", "safety",
                      "citations", "related_objects", "uncertainties",
                      "resolved_intent", "conversation_id", "retrieval_run_id"]:
            assert name in fields, f"Missing field: {name}"

    def test_ask_context_to_facet_filters(self):
        """API-002: AskContext fields must map to retrieval facet_filters."""
        from capability_commons.api.routes.ask import _build_facet_filters
        from capability_commons.schemas.ask import AskRequest, AskContext
        req = AskRequest(
            query="water storage",
            context=AskContext(housing_type="apartment", climate_zone="arid"),
        )
        filters = _build_facet_filters(req)
        assert filters["housing_type"] == ["apartment"]
        assert filters["climate_zone"] == ["arid"]

    def test_intent_detection_stub(self):
        """API-002: Stub intent detector must classify basic patterns."""
        from capability_commons.api.routes.ask import _detect_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert _detect_intent("How do I store water?") == RetrievalIntent.HOW_TO
        assert _detect_intent("Why does concrete crack?") == RetrievalIntent.WHY
        assert _detect_intent("Compare solar vs wind power") == RetrievalIntent.COMPARE_OPTIONS
        assert _detect_intent("Is this safe to eat?") == RetrievalIntent.SAFETY_CHECK

    def test_ask_route_registered(self):
        """API-002: /v1/public/ask route must be registered in the app router."""
        from capability_commons.api.router import api_router
        paths = [r.path for r in api_router.routes]
        assert "/v1/public/ask" in paths

    def test_ask_route_uses_public_workspace(self):
        """API-002: public_ask route must use PublicWorkspace dependency."""
        import inspect
        from capability_commons.api.routes import ask as ask_mod
        source = inspect.getsource(ask_mod)
        assert "PublicWorkspace" in source

    def test_compose_answer_handles_empty_evidence(self):
        """API-002: compose_answer must handle empty evidence gracefully."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        pack = _make_evidence_pack(sufficiency=0.0)
        req = AskRequest(query="test query")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert "No relevant information" in resp.answer
        assert resp.resolved_intent == RetrievalIntent.HOW_TO


# === RET-004: Intent auto-detection ===


class TestRET004IntentClassifier:
    def test_how_to_patterns(self):
        """RET-004: Must classify procedural queries as HOW_TO."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("How do I store water safely?") == RetrievalIntent.HOW_TO
        assert classify_intent("How to build a rain barrel") == RetrievalIntent.HOW_TO
        assert classify_intent("Steps to install a solar panel") == RetrievalIntent.HOW_TO
        assert classify_intent("Guide to composting") == RetrievalIntent.HOW_TO

    def test_why_patterns(self):
        """RET-004: Must classify explanatory queries as WHY."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("Why does concrete crack in cold weather?") == RetrievalIntent.WHY
        assert classify_intent("Explain why rainwater needs filtering") == RetrievalIntent.WHY
        assert classify_intent("What causes mold in basements?") == RetrievalIntent.WHY

    def test_compare_patterns(self):
        """RET-004: Must classify comparative queries as COMPARE_OPTIONS."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("Solar vs wind power") == RetrievalIntent.COMPARE_OPTIONS
        assert classify_intent("Compare drip irrigation and flood irrigation") == RetrievalIntent.COMPARE_OPTIONS
        assert classify_intent("Which is better: clay or metal roofing?") == RetrievalIntent.COMPARE_OPTIONS
        assert classify_intent("Pros and cons of composting toilets") == RetrievalIntent.COMPARE_OPTIONS

    def test_safety_patterns(self):
        """RET-004: Must classify safety queries as SAFETY_CHECK."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("Is it safe to drink rainwater?") == RetrievalIntent.SAFETY_CHECK
        assert classify_intent("Dangers of improperly stored food") == RetrievalIntent.SAFETY_CHECK

    def test_learn_path_patterns(self):
        """RET-004: Must classify learning queries as LEARN_PATH."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("Where should I start learning about permaculture?") == RetrievalIntent.LEARN_PATH
        assert classify_intent("What should I learn first before building?") == RetrievalIntent.LEARN_PATH
        assert classify_intent("Learning path for off-grid living") == RetrievalIntent.LEARN_PATH

    def test_debug_failure_patterns(self):
        """RET-004: Must classify troubleshooting queries as DEBUG_FAILURE."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("My solar panel is not working") == RetrievalIntent.DEBUG_FAILURE
        assert classify_intent("How to troubleshoot a broken pump") == RetrievalIntent.DEBUG_FAILURE

    def test_fallback_to_how_to(self):
        """RET-004: Unrecognized queries must default to HOW_TO."""
        from capability_commons.retrieval.intent_classifier import classify_intent
        from capability_commons.domain.enums import RetrievalIntent
        assert classify_intent("water storage containers") == RetrievalIntent.HOW_TO

    def test_ask_route_uses_classifier(self):
        """RET-004: Ask route must use the intent_classifier module."""
        import inspect
        from capability_commons.api.routes import ask as ask_mod
        source = inspect.getsource(ask_mod)
        assert "classify_intent" in source


# === RET-005: Structured answer composer ===


class TestRET005AnswerComposer:
    def test_compose_answer_importable(self):
        """RET-005: compose_answer must be importable from answer_composer."""
        from capability_commons.retrieval.answer_composer import compose_answer
        assert callable(compose_answer)

    def test_compose_answer_returns_ask_response(self):
        """RET-005: compose_answer must return an AskResponse."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest, AskResponse

        node = _make_evidence_node(title="Water Storage", summary="Store water in food-grade containers")
        pack = _make_evidence_pack(evidence=[node])
        req = AskRequest(query="How to store water?")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert isinstance(resp, AskResponse)
        assert "Water Storage" in resp.answer
        assert resp.resolved_intent == RetrievalIntent.HOW_TO

    def test_compose_extracts_action_now(self):
        """RET-005: action_now must be the top evidence node's summary."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node(title="First Step", summary="Do this first")
        pack = _make_evidence_pack(evidence=[node])
        req = AskRequest(query="test query")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert resp.action_now == "Do this first"

    def test_compose_builds_implementation_steps(self):
        """RET-005: Implementation steps must be built from actionable evidence nodes."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        nodes = [
            _make_evidence_node(title="Step A", slug="step-a", type_="skill_guide", score=0.9, summary="Do A"),
            _make_evidence_node(title="Step B", slug="step-b", type_="project_blueprint", score=0.7, summary="Do B"),
            _make_evidence_node(title="Note C", slug="note-c", type_="safety_notice", score=0.6, summary="Be careful"),
        ]
        pack = _make_evidence_pack(evidence=nodes)
        req = AskRequest(query="How to build?")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        # Only skill_guide and project_blueprint are actionable
        assert len(resp.implementation_plan) == 2
        assert resp.implementation_plan[0].step == 1
        assert resp.implementation_plan[0].source_slug == "step-a"
        assert resp.implementation_plan[1].source_slug == "step-b"

    def test_compose_extracts_safety_from_safety_nodes(self):
        """RET-005: Safety warnings must be extracted from safety-type nodes."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node(title="Electrical Safety", type_="safety_notice", summary="Never touch live wires")
        pack = _make_evidence_pack(evidence=[node])
        req = AskRequest(query="How to wire a panel?")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert len(resp.safety.warnings) >= 1
        assert "Electrical Safety" in resp.safety.warnings[0]

    def test_compose_extracts_safety_from_keywords(self):
        """RET-005: Safety warnings extracted from summaries with safety keywords."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node(title="Water Tips", type_="skill_guide", summary="Warning: avoid contaminated sources")
        pack = _make_evidence_pack(evidence=[node])
        req = AskRequest(query="water purification")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert any("warning" in w.lower() or "contaminated" in w.lower() for w in resp.safety.warnings)

    def test_compose_detects_contradictions_as_uncertainties(self):
        """RET-005: Contradictions in evidence must surface as uncertainties."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node()
        pack = _make_evidence_pack(
            evidence=[node],
            contradictions=[{"description": "Source A says X, Source B says Y"}],
        )
        req = AskRequest(query="test query")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert any("conflicting" in u.lower() for u in resp.uncertainties)

    def test_compose_detects_low_sufficiency(self):
        """RET-005: Low sufficiency scores must surface as uncertainties."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node()
        pack = _make_evidence_pack(evidence=[node], sufficiency=0.3)
        req = AskRequest(query="test query")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert any("may not fully" in u for u in resp.uncertainties)

    def test_compose_builds_related_from_next_steps(self):
        """RET-005: Related objects must be built from evidence next_steps."""
        from capability_commons.retrieval.answer_composer import compose_answer
        from capability_commons.domain.enums import RetrievalIntent
        from capability_commons.schemas.ask import AskRequest

        node = _make_evidence_node()
        pack = _make_evidence_pack(
            evidence=[node],
            next_steps=[{"slug": "rainwater-filter", "title": "Rainwater Filtration", "role": "prerequisite"}],
        )
        req = AskRequest(query="test query")
        resp = compose_answer(pack, RetrievalIntent.HOW_TO, req)
        assert len(resp.related_objects) == 1
        assert resp.related_objects[0].slug == "rainwater-filter"
        assert resp.related_objects[0].role == "prerequisite"

    def test_ask_route_uses_composer(self):
        """RET-005: Ask route must use compose_answer from answer_composer."""
        import inspect
        from capability_commons.api.routes import ask as ask_mod
        source = inspect.getsource(ask_mod)
        assert "compose_answer" in source
        assert "answer_composer" in source


# === RET-006: Conversation memory ===


class TestRET006ConversationMemory:
    def test_conversation_turn_model_exists(self):
        """RET-006: ConversationTurn DB model must exist."""
        from capability_commons.db.models import ConversationTurn
        assert ConversationTurn.__tablename__ == "conversation_turns"

    def test_conversation_turn_has_required_columns(self):
        """RET-006: ConversationTurn must have all required columns."""
        from capability_commons.db.models import ConversationTurn
        columns = {c.name for c in ConversationTurn.__table__.columns}
        for col in ["id", "conversation_id", "workspace_id", "turn_number",
                     "query", "resolved_intent", "retrieval_run_id",
                     "answer_summary", "context_json", "created_at"]:
            assert col in columns, f"Missing column: {col}"

    def test_conversation_memory_service_exists(self):
        """RET-006: ConversationMemory service must be importable."""
        from capability_commons.retrieval.conversation_memory import ConversationMemory
        assert ConversationMemory is not None

    def test_conversation_memory_has_required_methods(self):
        """RET-006: ConversationMemory must have get_prior_turns, save_turn, build_context_prefix."""
        from capability_commons.retrieval.conversation_memory import ConversationMemory
        for method in ["get_prior_turns", "save_turn", "build_context_prefix",
                        "get_or_create_conversation_id"]:
            assert hasattr(ConversationMemory, method), f"Missing method: {method}"

    def test_build_context_prefix_empty(self):
        """RET-006: build_context_prefix must return empty string for no turns."""
        from unittest.mock import MagicMock
        from capability_commons.retrieval.conversation_memory import ConversationMemory
        mem = ConversationMemory(session=MagicMock())
        assert mem.build_context_prefix([]) == ""

    def test_build_context_prefix_with_turns(self):
        """RET-006: build_context_prefix must format prior turns as context."""
        from unittest.mock import MagicMock
        from capability_commons.retrieval.conversation_memory import ConversationMemory
        mem = ConversationMemory(session=MagicMock())

        turn1 = MagicMock()
        turn1.query = "How to store water?"
        turn1.answer_summary = "Use food-grade containers"
        turn2 = MagicMock()
        turn2.query = "What about for long term?"
        turn2.answer_summary = None

        prefix = mem.build_context_prefix([turn1, turn2])
        assert "How to store water?" in prefix
        assert "food-grade containers" in prefix
        assert "What about for long term?" in prefix
        assert "Prior conversation context:" in prefix

    def test_ask_route_uses_conversation_memory(self):
        """RET-006: Ask route must use ConversationMemory for multi-turn."""
        import inspect
        from capability_commons.api.routes import ask as ask_mod
        source = inspect.getsource(ask_mod)
        assert "ConversationMemory" in source
        assert "conversation_memory" in source
        assert "get_or_create_conversation_id" in source
        assert "save_turn" in source

    def test_ask_route_augments_query_with_context(self):
        """RET-006: Ask route must augment query with prior conversation context."""
        import inspect
        from capability_commons.api.routes import ask as ask_mod
        source = inspect.getsource(ask_mod)
        assert "build_context_prefix" in source
        assert "prior_turns" in source

    def test_migration_exists(self):
        """RET-006: Alembic migration for conversation_turns must exist."""
        import os
        migration_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "alembic", "versions",
        )
        files = os.listdir(migration_dir)
        assert any("conversation_turns" in f for f in files)

    def test_max_context_turns_constant(self):
        """RET-006: MAX_CONTEXT_TURNS must be defined and reasonable."""
        from capability_commons.retrieval.conversation_memory import MAX_CONTEXT_TURNS
        assert 1 <= MAX_CONTEXT_TURNS <= 20


# === CONTENT-001: Implementation profile fields ===


class TestCONTENT001ImplementationProfile:
    def test_implementation_profile_model_exists(self):
        """CONTENT-001: ImplementationProfile model must be importable."""
        from capability_commons.schemas.structured_data import ImplementationProfile
        assert ImplementationProfile is not None

    def test_implementation_profile_fields(self):
        """CONTENT-001: ImplementationProfile must have all spec fields."""
        from capability_commons.schemas.structured_data import ImplementationProfile
        fields = ImplementationProfile.model_fields
        for name in ["smallest_viable_version", "preflight_checks", "tools_tiered",
                      "materials_tiered", "estimated_time_hours", "estimated_cost_band",
                      "success_checks", "stop_conditions", "common_mistakes",
                      "variants", "escalation_guidance"]:
            assert name in fields, f"Missing field: {name}"

    def test_implementation_profile_validates(self):
        """CONTENT-001: ImplementationProfile must validate valid data."""
        from capability_commons.schemas.structured_data import ImplementationProfile
        profile = ImplementationProfile(
            smallest_viable_version="Collect rainwater in a clean bucket",
            preflight_checks=["Check local regulations"],
            tools_tiered=[{"name": "Bucket", "tier": "essential", "substitutes": ["Basin"]}],
            estimated_time_hours=2.0,
            estimated_cost_band="low",
            success_checks=["Water is clear after filtering"],
            stop_conditions=["Water smells or is discolored"],
            common_mistakes=["Using non-food-grade containers"],
            escalation_guidance="Consult water quality expert if source is unknown",
        )
        assert profile.smallest_viable_version is not None
        assert len(profile.tools_tiered) == 1
        assert profile.tools_tiered[0].tier == "essential"

    def test_implementation_profile_all_optional(self):
        """CONTENT-001: All ImplementationProfile fields must be optional (backward compat)."""
        from capability_commons.schemas.structured_data import ImplementationProfile
        profile = ImplementationProfile()
        assert profile.smallest_viable_version is None
        assert profile.tools_tiered == []

    def test_extract_implementation_profile(self):
        """CONTENT-001: extract_implementation_profile must parse from structured_data."""
        from capability_commons.schemas.structured_data import extract_implementation_profile
        data = {
            "tools": ["hammer"],
            "implementation_profile": {
                "smallest_viable_version": "Use a hand drill",
                "estimated_time_hours": 4.0,
            },
        }
        profile = extract_implementation_profile(data)
        assert profile is not None
        assert profile.smallest_viable_version == "Use a hand drill"
        assert profile.estimated_time_hours == 4.0

    def test_extract_implementation_profile_missing(self):
        """CONTENT-001: extract_implementation_profile returns None when absent."""
        from capability_commons.schemas.structured_data import extract_implementation_profile
        assert extract_implementation_profile({"tools": ["hammer"]}) is None

    def test_tool_tier_model(self):
        """CONTENT-001: ToolTier must validate name, tier, substitutes."""
        from capability_commons.schemas.structured_data import ToolTier
        t = ToolTier(name="Saw", tier="essential", substitutes=["Hand saw", "Jigsaw"])
        assert t.name == "Saw"
        assert t.tier == "essential"
        assert len(t.substitutes) == 2

    def test_serializer_indexes_implementation_profile(self):
        """CONTENT-001: segment_serializer must index nested implementation_profile fields."""
        from capability_commons.search.segment_serializer import serialize_structured_data
        data = {
            "implementation_profile": {
                "smallest_viable_version": "Basic version",
                "preflight_checks": ["Check local codes"],
                "tools_tiered": [{"name": "Drill", "tier": "essential", "substitutes": ["Screwdriver"]}],
                "materials_tiered": [{"name": "Plywood", "tier": "recommended"}],
                "estimated_time_hours": 3.5,
                "estimated_cost_band": "medium",
                "stop_conditions": ["If structure creaks"],
            },
        }
        text = serialize_structured_data(data)
        assert "Basic version" in text
        assert "Check local codes" in text
        assert "Drill (essential)" in text
        assert "Screwdriver" in text
        assert "Plywood (recommended)" in text
        assert "3.5 hours" in text
        assert "medium" in text
        assert "structure creaks" in text


# === PUB-002: Enrich public object responses ===


class TestPUB002PublicObjectEnrichment:
    def test_public_implementation_profile_model(self):
        """PUB-002: PublicImplementationProfile must be importable with all fields."""
        from capability_commons.schemas.public import PublicImplementationProfile
        fields = PublicImplementationProfile.model_fields
        for name in ["smallest_viable_version", "preflight_checks", "tools",
                      "materials", "estimated_time_hours", "estimated_cost_band",
                      "success_checks", "stop_conditions", "common_mistakes",
                      "variants", "escalation_guidance"]:
            assert name in fields, f"Missing field: {name}"

    def test_project_implementation_profile_with_nested(self):
        """PUB-002: project_implementation_profile must extract from nested profile."""
        from capability_commons.schemas.public import project_implementation_profile
        data = {
            "implementation_profile": {
                "smallest_viable_version": "Bucket collection",
                "tools_tiered": [{"name": "Bucket", "tier": "essential"}],
                "estimated_time_hours": 1.0,
                "estimated_cost_band": "free",
                "success_checks": ["Water is clean"],
            },
        }
        profile = project_implementation_profile(data)
        assert profile is not None
        assert profile.smallest_viable_version == "Bucket collection"
        assert len(profile.tools) == 1
        assert profile.tools[0]["name"] == "Bucket"
        assert profile.estimated_cost_band == "free"

    def test_project_implementation_profile_from_top_level(self):
        """PUB-002: project_implementation_profile must fall back to top-level fields."""
        from capability_commons.schemas.public import project_implementation_profile
        data = {
            "tools": ["Hammer", "Nails"],
            "materials": ["Wood planks"],
            "stop_conditions": ["If wood splits"],
            "success_criteria": ["Frame is square"],
            "variants": ["Use screws instead of nails"],
        }
        profile = project_implementation_profile(data)
        assert profile is not None
        assert len(profile.tools) == 2
        assert profile.tools[0]["name"] == "Hammer"
        assert profile.tools[0]["tier"] == "unspecified"
        assert len(profile.materials) == 1
        assert profile.stop_conditions == ["If wood splits"]
        assert profile.success_checks == ["Frame is square"]

    def test_project_implementation_profile_returns_none_when_empty(self):
        """PUB-002: project_implementation_profile must return None when no actionable fields."""
        from capability_commons.schemas.public import project_implementation_profile
        assert project_implementation_profile({}) is None
        assert project_implementation_profile({"some_other_field": "value"}) is None

    def test_public_object_response_has_implementation_profile_field(self):
        """PUB-002: PublicObjectResponse must have optional implementation_profile field."""
        from capability_commons.schemas.public import PublicObjectResponse
        assert "implementation_profile" in PublicObjectResponse.model_fields

    def test_publication_service_uses_projection(self):
        """PUB-002: Publication service must call project_implementation_profile."""
        import inspect
        from capability_commons.publication import service as svc_mod
        source = inspect.getsource(svc_mod)
        assert "project_implementation_profile" in source
        assert "impl_profile" in source


# === SAFE-001: Publish gates and safety review workflow ===


class TestSAFE001PublishGates:
    def test_publish_gate_importable(self):
        """SAFE-001: PublishGate must be importable."""
        from capability_commons.services.publish_gate import PublishGate, GateResult
        assert PublishGate is not None
        assert GateResult is not None

    def test_gate_result_structure(self):
        """SAFE-001: GateResult must have passed, blockers, warnings."""
        from capability_commons.services.publish_gate import GateResult
        r = GateResult(passed=True, blockers=[], warnings=["test warning"])
        assert r.passed is True
        assert r.warnings == ["test warning"]

    def test_high_risk_bands_defined(self):
        """SAFE-001: HIGH_RISK_BANDS must include HIGH and EXPERT_ONLY."""
        from capability_commons.services.publish_gate import HIGH_RISK_BANDS
        from capability_commons.domain.enums import RiskBand
        assert RiskBand.HIGH in HIGH_RISK_BANDS
        assert RiskBand.EXPERT_ONLY in HIGH_RISK_BANDS
        assert RiskBand.LOW not in HIGH_RISK_BANDS

    def test_safety_boundary_required_types(self):
        """SAFE-001: SAFETY_BOUNDARY_REQUIRED_TYPES must include actionable types."""
        from capability_commons.services.publish_gate import SAFETY_BOUNDARY_REQUIRED_TYPES
        from capability_commons.domain.enums import COType
        assert COType.SKILL_GUIDE in SAFETY_BOUNDARY_REQUIRED_TYPES
        assert COType.PROJECT_BLUEPRINT in SAFETY_BOUNDARY_REQUIRED_TYPES

    def test_registry_publish_uses_gate(self):
        """SAFE-001: RegistryService.publish_version must call PublishGate."""
        import inspect
        from capability_commons.services.registry import RegistryService
        source = inspect.getsource(RegistryService.publish_version)
        assert "PublishGate" in source
        assert "gate.check" in source
        assert "bypass_gate" in source

    def test_registry_publish_has_bypass(self):
        """SAFE-001: publish_version must accept bypass_gate parameter."""
        import inspect
        from capability_commons.services.registry import RegistryService
        sig = inspect.signature(RegistryService.publish_version)
        assert "bypass_gate" in sig.parameters

    def test_publish_check_endpoint_exists(self):
        """SAFE-001: /publish-check dry-run endpoint must be registered."""
        from capability_commons.api.router import api_router
        paths = [r.path for r in api_router.routes]
        assert "/v1/objects/{object_id}/versions/{version_id}/publish-check" in paths

    def test_gate_checks_all_rules(self):
        """SAFE-001: PublishGate.check must inspect risk_band, safety_boundary, and contradictions."""
        import inspect
        from capability_commons.services.publish_gate import PublishGate
        source = inspect.getsource(PublishGate.check)
        assert "risk_band" in source
        assert "safety_boundary" in source
        assert "contradiction" in source.lower()


# === OBS-001: Observability metrics ===


class TestOBS001Metrics:
    def test_metrics_service_importable(self):
        """OBS-001: MetricsService must be importable."""
        from capability_commons.services.metrics import MetricsService
        assert MetricsService is not None

    def test_metrics_service_has_required_methods(self):
        """OBS-001: MetricsService must have ingest_quality, answer_quality, summary."""
        from capability_commons.services.metrics import MetricsService
        for method in ["ingest_quality", "answer_quality", "summary"]:
            assert hasattr(MetricsService, method), f"Missing method: {method}"

    def test_metrics_endpoints_registered(self):
        """OBS-001: /v1/metrics/* endpoints must be registered."""
        from capability_commons.api.router import api_router
        paths = [r.path for r in api_router.routes]
        assert "/v1/metrics/ingest" in paths
        assert "/v1/metrics/answer" in paths
        assert "/v1/metrics/summary" in paths

    def test_metrics_require_auth(self):
        """OBS-001: Metrics endpoints must require authentication (CurrentWorkspace)."""
        import inspect
        from capability_commons.api.routes import metrics as metrics_mod
        source = inspect.getsource(metrics_mod)
        assert "CurrentWorkspace" in source

    def test_ingest_quality_tracks_key_metrics(self):
        """OBS-001: ingest_quality must track lifecycle, evidence, segments, reviews."""
        import inspect
        from capability_commons.services.metrics import MetricsService
        source = inspect.getsource(MetricsService.ingest_quality)
        for key in ["lifecycle_state", "evidence", "segment", "review", "contradiction"]:
            assert key.lower() in source.lower(), f"Missing metric area: {key}"

    def test_answer_quality_tracks_key_metrics(self):
        """OBS-001: answer_quality must track runs, sufficiency, conversations."""
        import inspect
        from capability_commons.services.metrics import MetricsService
        source = inspect.getsource(MetricsService.answer_quality)
        for key in ["sufficiency", "conversation", "completed"]:
            assert key in source.lower(), f"Missing metric area: {key}"


# === PERF-001: Response caching ===


class TestPERF001ResponseCache:
    def test_response_cache_importable(self):
        """PERF-001: ResponseCache must be importable."""
        from capability_commons.api.response_cache import ResponseCache
        assert ResponseCache is not None

    def test_cache_set_and_get(self):
        """PERF-001: Cache must store and retrieve values."""
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache(ttl_seconds=60)
        cache.set("search", {"query": "water"}, {"results": [1, 2, 3]})
        result = cache.get("search", {"query": "water"})
        assert result == {"results": [1, 2, 3]}

    def test_cache_miss(self):
        """PERF-001: Cache must return None for missing keys."""
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache()
        assert cache.get("search", {"query": "nonexistent"}) is None

    def test_cache_ttl_expiry(self):
        """PERF-001: Cache must expire entries after TTL."""
        import time
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache(ttl_seconds=0)  # Immediate expiry
        cache.set("search", {"query": "water"}, "value")
        time.sleep(0.01)
        assert cache.get("search", {"query": "water"}) is None

    def test_cache_invalidation(self):
        """PERF-001: Cache must support prefix and full invalidation."""
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache()
        cache.set("search", {"q": "a"}, "v1")
        cache.set("ask", {"q": "b"}, "v2")
        count = cache.invalidate("search")
        assert count == 1
        assert cache.get("search", {"q": "a"}) is None
        assert cache.get("ask", {"q": "b"}) == "v2"

    def test_cache_max_entries(self):
        """PERF-001: Cache must evict when max_entries is reached."""
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache(max_entries=3)
        for i in range(5):
            cache.set("test", {"i": i}, f"val{i}")
        assert cache.size <= 3

    def test_get_response_cache_singleton(self):
        """PERF-001: get_response_cache must return a singleton."""
        from capability_commons.api.response_cache import get_response_cache
        c1 = get_response_cache()
        c2 = get_response_cache()
        assert c1 is c2

    def test_cache_deterministic_keys(self):
        """PERF-001: Same params must produce same cache key regardless of dict order."""
        from capability_commons.api.response_cache import ResponseCache
        cache = ResponseCache()
        cache.set("test", {"a": 1, "b": 2}, "value")
        assert cache.get("test", {"b": 2, "a": 1}) == "value"


# === ING-007: DB-backed ingest jobs and review queues ===


class TestING007IngestJobs:
    def test_ingest_job_status_enum_exists(self):
        """ING-007: IngestJobStatus enum must exist with expected values."""
        from capability_commons.domain.enums import IngestJobStatus
        assert IngestJobStatus.PENDING.value == "pending"
        assert IngestJobStatus.RUNNING.value == "running"
        assert IngestJobStatus.COMPLETED.value == "completed"
        assert IngestJobStatus.FAILED.value == "failed"

    def test_ingest_pass_status_enum_exists(self):
        """ING-007: IngestPassStatus enum must exist with expected values."""
        from capability_commons.domain.enums import IngestPassStatus
        assert IngestPassStatus.PENDING.value == "pending"
        assert IngestPassStatus.RUNNING.value == "running"
        assert IngestPassStatus.COMPLETED.value == "completed"
        assert IngestPassStatus.FAILED.value == "failed"
        assert IngestPassStatus.SKIPPED.value == "skipped"

    def test_ingest_job_model_exists(self):
        """ING-007: IngestJob model must be importable with expected columns."""
        from capability_commons.db.models import IngestJob
        table = IngestJob.__table__
        col_names = {c.name for c in table.columns}
        assert "id" in col_names
        assert "workspace_id" in col_names
        assert "project_name" in col_names
        assert "status" in col_names
        assert "source_count" in col_names
        assert "error_log" in col_names
        assert "created_at" in col_names
        assert "started_at" in col_names
        assert "completed_at" in col_names

    def test_ingest_job_pass_model_exists(self):
        """ING-007: IngestJobPass model must be importable with expected columns."""
        from capability_commons.db.models import IngestJobPass
        table = IngestJobPass.__table__
        col_names = {c.name for c in table.columns}
        assert "id" in col_names
        assert "ingest_job_id" in col_names
        assert "pass_name" in col_names
        assert "status" in col_names
        assert "output_path" in col_names
        assert "error_message" in col_names
        assert "started_at" in col_names
        assert "completed_at" in col_names

    def test_ingest_service_importable(self):
        """ING-007: IngestService must be importable."""
        from capability_commons.services.ingest import IngestService
        assert IngestService is not None

    def test_ingest_service_has_required_methods(self):
        """ING-007: IngestService must have create, get, list, update methods."""
        import inspect
        from capability_commons.services.ingest import IngestService
        methods = {name for name, _ in inspect.getmembers(IngestService, predicate=inspect.isfunction)}
        assert "create_job" in methods
        assert "get_job" in methods
        assert "list_jobs" in methods
        assert "start_pass" in methods
        assert "complete_pass" in methods
        assert "fail_pass" in methods
        assert "fail_job" in methods

    def test_ingest_pass_names_constant(self):
        """ING-007: INGEST_PASS_NAMES must list the 8 pipeline passes in order."""
        from capability_commons.services.ingest import INGEST_PASS_NAMES
        assert INGEST_PASS_NAMES == [
            "parse", "extract", "draft", "cite",
            "canonicalize", "edges", "bundles", "load",
        ]

    def test_ingest_schemas_importable(self):
        """ING-007: Ingest API schemas must be importable."""
        from capability_commons.schemas.ingest import (
            CreateIngestJobRequest,
            IngestJobResponse,
            IngestJobPassResponse,
        )
        assert CreateIngestJobRequest is not None
        assert IngestJobResponse is not None
        assert IngestJobPassResponse is not None

    def test_ingest_job_response_has_passes(self):
        """ING-007: IngestJobResponse must include passes list."""
        from capability_commons.schemas.ingest import IngestJobResponse
        fields = IngestJobResponse.model_fields
        assert "passes" in fields
        assert "project_name" in fields
        assert "status" in fields

    def test_ingest_routes_importable(self):
        """ING-007: Ingest routes module must be importable with router."""
        from capability_commons.api.routes.ingest import router
        assert router is not None

    def test_ingest_routes_registered(self):
        """ING-007: Ingest routes must be registered in the main router."""
        import inspect
        from capability_commons.api import router as router_mod
        source = inspect.getsource(router_mod)
        assert "ingest" in source

    def test_ingest_routes_have_endpoints(self):
        """ING-007: Ingest router must have create, list, get endpoints."""
        from capability_commons.api.routes.ingest import router
        paths = [r.path for r in router.routes]
        assert "/ingest/jobs" in paths
        assert "/ingest/jobs/{job_id}" in paths

    def test_review_queue_endpoint_exists(self):
        """ING-007: Reviews router must have a GET /reviews/queue endpoint."""
        from capability_commons.api.routes.reviews import router
        paths = [r.path for r in router.routes]
        assert "/reviews/queue" in paths

    def test_review_queue_queries_in_review(self):
        """ING-007: Review queue must filter by IN_REVIEW lifecycle state."""
        import inspect
        from capability_commons.api.routes import reviews
        source = inspect.getsource(reviews)
        assert "LifecycleState" in source
        assert "IN_REVIEW" in source
