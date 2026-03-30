"""Tests for LLM passes with mocked responses."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import orjson
import polars as pl
import pytest
import yaml

from capability_commons.cli.ingest.models import (
    BundleOutput,
    ClaimCitation,
    CitationSpan,
    CanonicalizationDecision,
    ExtractionRow,
    ExtractedEdge,
    SourceSegment,
)
from capability_commons.cli.ingest.project import IngestProject


@pytest.fixture
def project_with_segments(tmp_path):
    """Create a project with pre-generated segments."""
    proj = IngestProject.init(
        projects_root=tmp_path / "projects",
        name="test-passes",
        sources=[{
            "id": "src.test",
            "file": "sources/test.pdf",
            "title": "Test Book",
            "source_kind": "BOOK",
        }],
    )
    segments = [
        SourceSegment(
            source_id="src.test",
            segment_id="seg_000001",
            page_start=1,
            page_end=1,
            heading_path=["Chapter 1", "Water Storage"],
            text="Water should be stored in food-grade containers for at least 72 hours.",
            start_char=0,
            end_char=70,
        ),
        SourceSegment(
            source_id="src.test",
            segment_id="seg_000002",
            page_start=2,
            page_end=2,
            heading_path=["Chapter 1", "Treatment"],
            text="Treat water with chlorine or boiling before long-term storage.",
            start_char=71,
            end_char=131,
        ),
    ]
    with open(proj.segments_file, "wb") as f:
        for seg in segments:
            f.write(orjson.dumps(seg.model_dump()) + b"\n")
    proj.mark_pass_complete("parse")
    return proj


class TestExtractPass:
    async def test_writes_matrix_csv(self, project_with_segments):
        from capability_commons.cli.ingest.extract import ExtractionResponse, run_extract
        from capability_commons.cli.ingest.llm_client import LLMClient

        mock_result = ExtractionResponse(rows=[
            ExtractionRow(
                source_id="src.test",
                section_id="sec_001",
                start_page=1,
                end_page=1,
                heading_path="Chapter 1 > Water Storage",
                segment_ids=["seg_000001"],
                candidate_slug="water.safe-storage",
                candidate_type="skill_guide",
                primary_domain="water",
                stage="household",
                summary="How to store water safely.",
                confidence=0.9,
            ),
        ])

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_extract(project_with_segments, client, yes=True)

        assert project_with_segments.matrix_file.exists()
        df = pl.read_csv(project_with_segments.matrix_file)
        assert len(df) >= 1
        assert "water.safe-storage" in df["candidate_slug"].to_list()

    async def test_sections_filter(self, project_with_segments):
        from capability_commons.cli.ingest.extract import ExtractionResponse, run_extract
        from capability_commons.cli.ingest.llm_client import LLMClient

        mock_result = ExtractionResponse(rows=[
            ExtractionRow(
                source_id="src.test",
                section_id="sec_001",
                start_page=2,
                end_page=2,
                heading_path="Chapter 1 > Treatment",
                segment_ids=["seg_000002"],
                candidate_slug="water.treatment",
                candidate_type="skill_guide",
                primary_domain="water",
                stage="household",
                summary="Water treatment methods.",
                confidence=0.85,
            ),
        ])

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        generate_mock = AsyncMock(return_value=mock_result)
        with patch.object(client, "generate", new=generate_mock):
            await run_extract(project_with_segments, client, sections_filter="Treatment", yes=True)

        # Only the Treatment section should be processed
        assert generate_mock.call_count == 1


class TestDraftPass:
    async def test_writes_draft_yaml(self, project_with_segments):
        from capability_commons.cli.ingest.draft import run_draft
        from capability_commons.cli.ingest.llm_client import LLMClient
        from pydantic import BaseModel

        # Create matrix first
        matrix_data = [{
            "source_id": "src.test",
            "section_id": "sec_001",
            "start_page": 1,
            "end_page": 1,
            "heading_path": "Chapter 1 > Water Storage",
            "segment_ids": "seg_000001",
            "candidate_slug": "water.safe-storage",
            "candidate_type": "skill_guide",
            "primary_domain": "water",
            "stage": "household",
            "summary": "How to store water safely.",
            "confidence": 0.9,
        }]
        pl.DataFrame(matrix_data).write_csv(project_with_segments.matrix_file)

        class DraftObject(BaseModel, extra="allow"):
            id: str
            slug: str
            canonical_title: str
            markdown_body: str

        mock_result = DraftObject(
            id="water.safe-storage",
            slug="water.safe-storage",
            canonical_title="Emergency Water Storage",
            markdown_body="# What this is\nHow to store water safely.",
            co_type="skill_guide",
        )

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_draft(project_with_segments, client, yes=True)

        draft_file = project_with_segments.drafts_dir / "water.safe-storage.yaml"
        assert draft_file.exists()
        obj = yaml.safe_load(draft_file.read_text())
        assert obj["canonical_title"] == "Emergency Water Storage"

    async def test_skip_existing(self, project_with_segments):
        from capability_commons.cli.ingest.draft import run_draft
        from capability_commons.cli.ingest.llm_client import LLMClient

        matrix_data = [{
            "source_id": "src.test",
            "section_id": "sec_001",
            "start_page": 1,
            "end_page": 1,
            "heading_path": "Chapter 1 > Water Storage",
            "segment_ids": "seg_000001",
            "candidate_slug": "water.safe-storage",
            "candidate_type": "skill_guide",
            "primary_domain": "water",
            "stage": "household",
            "summary": "How to store water safely.",
            "confidence": 0.9,
        }]
        pl.DataFrame(matrix_data).write_csv(project_with_segments.matrix_file)

        # Pre-create existing draft
        draft_file = project_with_segments.drafts_dir / "water.safe-storage.yaml"
        draft_file.write_text("slug: water.safe-storage\n")

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        generate_mock = AsyncMock()
        with patch.object(client, "generate", new=generate_mock):
            await run_draft(project_with_segments, client, skip_existing=True, yes=True)

        # LLM should not be called since the draft already exists
        assert generate_mock.call_count == 0


class TestCitePass:
    async def test_writes_citations(self, project_with_segments):
        from capability_commons.cli.ingest.cite import CitationResponse, run_cite
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create a draft file
        draft_obj = {
            "slug": "water.safe-storage",
            "canonical_title": "Emergency Water Storage",
            "markdown_body": "Store water in food-grade containers.",
        }
        draft_file = project_with_segments.drafts_dir / "water.safe-storage.yaml"
        with open(draft_file, "w") as f:
            yaml.dump(draft_obj, f)

        mock_result = CitationResponse(citations=[
            ClaimCitation(
                object_id="water.safe-storage",
                claim_id="clm_001",
                claim_text="Store water in food-grade containers",
                support=[
                    CitationSpan(
                        source_id="src.test",
                        page_start=1,
                        page_end=1,
                        segment_id="seg_000001",
                        excerpt="Water should be stored in food-grade containers",
                        start_char=0,
                        end_char=47,
                        support_strength="strong",
                    )
                ],
            ),
        ])

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_cite(project_with_segments, client, yes=True)

        # Check citations were written back to draft
        updated = yaml.safe_load(draft_file.read_text())
        assert len(updated["citations"]) == 1
        assert updated["citations"][0]["claim_id"] == "clm_001"

        # Check evidence map
        assert project_with_segments.evidence_map_file.exists()


class TestCanonicalizePass:
    async def test_no_duplicates_skips_llm(self, project_with_segments):
        from capability_commons.cli.ingest.canonicalize import run_canonicalize
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create two very different drafts
        for slug, title, domain in [
            ("water.storage", "Water Storage", "water"),
            ("energy.solar", "Solar Panels", "energy"),
        ]:
            draft = {"slug": slug, "canonical_title": title, "primary_domain": domain}
            with open(project_with_segments.drafts_dir / f"{slug}.yaml", "w") as f:
                yaml.dump(draft, f)

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        generate_mock = AsyncMock()
        with patch.object(client, "generate", new=generate_mock):
            await run_canonicalize(project_with_segments, client, yes=True)

        # Different domains → no groups → no LLM calls
        assert generate_mock.call_count == 0

    async def test_merges_similar_drafts(self, project_with_segments):
        from capability_commons.cli.ingest.canonicalize import CanonicalizeResponse, run_canonicalize
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create two similar drafts (same domain, similar titles)
        for slug, title in [
            ("water.safe-storage", "Emergency Water Storage"),
            ("water.water-storage", "Water Storage for Emergencies"),
        ]:
            draft = {
                "slug": slug,
                "canonical_title": title,
                "primary_domain": "water",
                "summary_short": "How to store water safely",
            }
            with open(project_with_segments.drafts_dir / f"{slug}.yaml", "w") as f:
                yaml.dump(draft, f)

        mock_result = CanonicalizeResponse(decisions=[
            CanonicalizationDecision(
                action="merge",
                rationale="These cover the same topic",
                canonical_slug="water.safe-storage",
                deprecated_draft_ids=["water.water-storage"],
            ),
        ])

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_canonicalize(project_with_segments, client, yes=True)

        # Deprecated draft should be moved to _merged
        merged_dir = project_with_segments.drafts_dir / "_merged"
        assert (merged_dir / "water.water-storage.yaml").exists()
        assert not (project_with_segments.drafts_dir / "water.water-storage.yaml").exists()


class TestEdgesPass:
    async def test_writes_edges_csv(self, project_with_segments):
        from capability_commons.cli.ingest.edges import EdgesResponse, run_edges
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create two drafts
        for slug, title in [
            ("water.storage", "Water Storage"),
            ("water.treatment", "Water Treatment"),
        ]:
            draft = {
                "slug": slug,
                "canonical_title": title,
                "co_type": "skill_guide",
                "summary_short": f"About {title.lower()}",
            }
            with open(project_with_segments.drafts_dir / f"{slug}.yaml", "w") as f:
                yaml.dump(draft, f)

        mock_result = EdgesResponse(edges=[
            ExtractedEdge(
                source_id="water.treatment",
                target_id="water.storage",
                edge_type="prerequisite_for",
                confidence=0.85,
            ),
        ])

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_edges(project_with_segments, client, yes=True)

        assert project_with_segments.edges_file.exists()
        df = pl.read_csv(project_with_segments.edges_file)
        assert len(df) >= 1
        assert "water.treatment" in df["source_id"].to_list()


class TestBundlesPass:
    async def test_writes_bundle_to_draft(self, project_with_segments):
        from capability_commons.cli.ingest.bundles import run_bundles
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create a skill_guide draft (eligible for bundles)
        draft = {
            "slug": "water.safe-storage",
            "canonical_title": "Emergency Water Storage",
            "co_type": "skill_guide",
            "markdown_body": "How to store water safely.",
        }
        draft_file = project_with_segments.drafts_dir / "water.safe-storage.yaml"
        with open(draft_file, "w") as f:
            yaml.dump(draft, f)

        mock_result = BundleOutput(
            hook="Clean water saves lives.",
            primer="Water storage is essential for emergency preparedness...",
            guide="Step 1: Get food-grade containers...",
            reference=["Use 1 gallon per person per day", "Replace every 6 months"],
            worksheet=["Find two 5-gallon containers", "Calculate your family's needs"],
            teach_forward_kit={
                "three_minute_version": "Quick overview of water storage.",
                "ten_minute_outline": ["Intro", "Demo", "Practice"],
                "discussion_prompts": ["What water sources exist near you?"],
            },
        )

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        with patch.object(client, "generate", new=AsyncMock(return_value=mock_result)):
            await run_bundles(project_with_segments, client, yes=True)

        updated = yaml.safe_load(draft_file.read_text())
        assert "bundle_overrides" in updated
        assert updated["bundle_overrides"]["hook"] == "Clean water saves lives."

    async def test_skips_non_bundleable_types(self, project_with_segments):
        from capability_commons.cli.ingest.bundles import run_bundles
        from capability_commons.cli.ingest.llm_client import LLMClient

        # Create a concept_note (not in BUNDLE_TYPES)
        draft = {
            "slug": "water.concept",
            "canonical_title": "Water Concept",
            "co_type": "concept_note",
        }
        with open(project_with_segments.drafts_dir / "water.concept.yaml", "w") as f:
            yaml.dump(draft, f)

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        generate_mock = AsyncMock()
        with patch.object(client, "generate", new=generate_mock):
            await run_bundles(project_with_segments, client, yes=True)

        # concept_note is not bundleable → no LLM calls
        assert generate_mock.call_count == 0


class TestValidateCommand:
    def test_reports_errors_for_invalid_enums(self, project_with_segments):
        from capability_commons.cli.ingest.validate import run_validate

        draft = {
            "slug": "water.bad",
            "canonical_title": "Bad Object",
            "co_type": "INVALID_TYPE",
            "stage": "nonexistent",
        }
        with open(project_with_segments.drafts_dir / "water.bad.yaml", "w") as f:
            yaml.dump(draft, f)

        report = run_validate(project_with_segments)
        assert report.objects_count == 1
        assert len(report.errors) >= 2  # invalid type + invalid stage

    def test_reports_missing_citations_as_warnings(self, project_with_segments):
        from capability_commons.cli.ingest.validate import run_validate

        draft = {
            "slug": "water.nocite",
            "canonical_title": "No Citations",
            "co_type": "skill_guide",
            "stage": "household",
        }
        with open(project_with_segments.drafts_dir / "water.nocite.yaml", "w") as f:
            yaml.dump(draft, f)

        report = run_validate(project_with_segments)
        assert any("no citations" in w for w in report.warnings)

    def test_valid_object_passes(self, project_with_segments):
        from capability_commons.cli.ingest.validate import run_validate

        draft = {
            "slug": "water.good",
            "canonical_title": "Good Object",
            "co_type": "skill_guide",
            "stage": "household",
            "cost_band": "low",
            "risk_band": "low",
            "plain_language": "This is about water storage.",
            "markdown_body": "# Water Storage\n\nStore water safely in food-grade containers.",
            "citations": [{"claim_id": "clm_001", "claim_text": "test", "source_id": "src.test"}],
        }
        with open(project_with_segments.drafts_dir / "water.good.yaml", "w") as f:
            yaml.dump(draft, f)

        report = run_validate(project_with_segments)
        assert len(report.errors) == 0
        assert report.citation_coverage == 1.0
