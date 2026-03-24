"""Tests for ingestion pipeline Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_commons.cli.ingest.models import (
    CanonicalizationDecision,
    CitationSpan,
    ClaimCitation,
    ExtractedEdge,
    ExtractionRow,
    ManifestSource,
    ProjectManifest,
    SourceSegment,
    ValidationReport,
)


class TestSourceSegment:
    def test_valid_segment(self):
        seg = SourceSegment(
            source_id="src.test.book",
            segment_id="seg_000001",
            page_start=1,
            page_end=1,
            heading_path=["Chapter 1", "Section A"],
            text="Some content here.",
            start_char=0,
            end_char=18,
        )
        assert seg.segment_id == "seg_000001"
        assert seg.figure_refs == []
        assert seg.table_refs == []

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SourceSegment(
                source_id="src.test",
                segment_id="seg_000001",
                page_start=1,
                page_end=1,
                heading_path=[],
                # text is missing
                start_char=0,
                end_char=0,
            )


class TestExtractionRow:
    def test_valid_row(self):
        row = ExtractionRow(
            source_id="src.test",
            section_id="sec_001",
            start_page=1,
            end_page=3,
            heading_path="Chapter 1 > Section A",
            segment_ids=["seg_001", "seg_002"],
            candidate_slug="water.storage-basics",
            candidate_type="skill_guide",
            primary_domain="water",
            stage="household",
            summary="How to store water safely.",
            confidence=0.91,
        )
        assert row.candidate_type == "skill_guide"
        assert row.needs_split is False

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ExtractionRow(
                source_id="src.test",
                section_id="sec_001",
                start_page=1,
                end_page=1,
                heading_path="Ch1",
                segment_ids=[],
                candidate_slug="x.y",
                candidate_type="invalid_type",
                primary_domain="water",
                stage="household",
                summary="Test",
                confidence=0.5,
            )


class TestCitationSpan:
    def test_valid_span(self):
        span = CitationSpan(
            source_id="src.test",
            page_start=10,
            page_end=10,
            segment_id="seg_010",
            excerpt="water should be stored",
            start_char=50,
            end_char=72,
            support_strength="strong",
        )
        assert span.support_strength == "strong"

    def test_invalid_strength(self):
        with pytest.raises(ValidationError):
            CitationSpan(
                source_id="src.test",
                page_start=1,
                page_end=1,
                segment_id="seg_001",
                excerpt="test",
                start_char=0,
                end_char=4,
                support_strength="very_strong",
            )


class TestClaimCitation:
    def test_valid_citation(self):
        cc = ClaimCitation(
            object_id="water.storage-basics",
            claim_id="clm_001",
            claim_text="Water should be stored in food-grade containers.",
            support=[
                CitationSpan(
                    source_id="src.test",
                    page_start=10,
                    page_end=10,
                    segment_id="seg_010",
                    excerpt="food-grade containers",
                    start_char=50,
                    end_char=71,
                    support_strength="strong",
                )
            ],
        )
        assert len(cc.support) == 1


class TestExtractedEdge:
    def test_valid_edge(self):
        edge = ExtractedEdge(
            source_id="water.storage-basics",
            target_id="water.treatment-selection",
            edge_type="prerequisite_for",
            confidence=0.85,
        )
        assert edge.sequence is None
        assert edge.condition is None

    def test_with_optional_fields(self):
        edge = ExtractedEdge(
            source_id="a",
            target_id="b",
            edge_type="next_step_for",
            sequence=1,
            condition="after storage is set up",
            confidence=0.77,
        )
        assert edge.sequence == 1


class TestCanonicalizationDecision:
    def test_merge(self):
        d = CanonicalizationDecision(
            action="merge",
            rationale="Same learner outcome.",
            canonical_slug="water.storage-basics",
            deprecated_draft_ids=["water.water-store", "water.storing-water"],
        )
        assert d.action == "merge"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            CanonicalizationDecision(
                action="delete",
                rationale="test",
                canonical_slug="x",
            )


class TestValidationReport:
    def test_valid_report(self):
        r = ValidationReport(
            objects_count=10,
            edges_count=25,
            citations_count=8,
            errors=[],
            warnings=["Object food.seed-x has no citations"],
            citation_coverage=0.80,
        )
        assert r.citation_coverage == 0.80


class TestProjectManifest:
    def test_valid_manifest(self):
        m = ProjectManifest(
            name="test-project",
            created="2026-03-23T12:00:00Z",
            sources=[
                ManifestSource(
                    id="src.test",
                    file="sources/test.pdf",
                    title="Test Book",
                    source_kind="BOOK",
                )
            ],
        )
        assert m.name == "test-project"
        assert m.passes.parse.completed is None

    def test_default_passes(self):
        m = ProjectManifest(
            name="test",
            created="2026-03-23T00:00:00Z",
            sources=[],
        )
        assert m.passes.extract.completed is None
        assert m.passes.load.completed is None
