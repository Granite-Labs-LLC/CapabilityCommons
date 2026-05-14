"""Tests for Pass 0: PDF parsing to segments."""
from __future__ import annotations

from unittest.mock import patch

import orjson
import pytest

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.parse import (
    markdown_to_segments,
    run_parse,
)
from capability_commons.cli.ingest.project import IngestProject


class TestMarkdownToSegments:
    def test_splits_on_headings(self):
        md = """# Chapter 1: Water Storage

Water should be stored safely.

## Section 1.1: Containers

Use food-grade containers.

## Section 1.2: Treatment

Treat water before storage.
"""
        segments = markdown_to_segments(
            md,
            source_id="src.test",
            base_page=1,
        )
        assert len(segments) >= 3
        assert segments[0].heading_path == ["Chapter 1: Water Storage"]
        assert "water" in segments[0].text.lower()

    def test_assigns_sequential_ids(self):
        md = "# A\nText A\n# B\nText B\n# C\nText C\n"
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        ids = [s.segment_id for s in segments]
        assert ids == ["src.test::seg_000001", "src.test::seg_000002", "src.test::seg_000003"]

    def test_preserves_page_boundaries(self):
        md = "# Heading\nSome text on page 5."
        segments = markdown_to_segments(md, source_id="src.test", base_page=5)
        assert segments[0].page_start == 5

    def test_html_page_markers_drive_per_segment_pages(self):
        md = (
            "<!-- PAGE 1 -->\n"
            "# Intro\nIntro content on page one.\n"
            "<!-- PAGE 2 -->\n"
            "# Body\nBody content on page two.\n"
            "<!-- PAGE 3 -->\n"
            "# Tail\nTail content on page three.\n"
        )
        segs = markdown_to_segments(md, source_id="src.test")
        assert [s.heading_path[0] for s in segs] == ["Intro", "Body", "Tail"]
        assert (segs[0].page_start, segs[0].page_end) == (1, 1)
        assert (segs[1].page_start, segs[1].page_end) == (2, 2)
        assert (segs[2].page_start, segs[2].page_end) == (3, 3)
        # Markers themselves must not appear in the emitted segment text.
        for s in segs:
            assert "<!-- PAGE" not in s.text

    def test_segment_spanning_two_pages_reports_range(self):
        md = (
            "<!-- PAGE 7 -->\n"
            "# Heading\nFirst paragraph on page seven.\n\n"
            "<!-- PAGE 8 -->\n"
            "Second paragraph continues on page eight.\n"
        )
        segs = markdown_to_segments(md, source_id="src.test")
        assert len(segs) == 1
        assert segs[0].page_start == 7
        assert segs[0].page_end == 8

    def test_marker_paginate_separators_are_normalized(self):
        # Format produced by marker-pdf with paginate_output=True.
        sep = "-" * 48
        md = (
            f"\n\n{{0}}{sep}\n\n"
            "# Intro\nIntro on first page.\n"
            f"\n\n{{1}}{sep}\n\n"
            "# Body\nBody on second page.\n"
        )
        segs = markdown_to_segments(md, source_id="src.test")
        assert [(s.page_start, s.page_end) for s in segs] == [(1, 1), (2, 2)]
        for s in segs:
            assert "{0}" not in s.text and "{1}" not in s.text
            assert sep not in s.text


class TestRunParse:
    def test_writes_segments_jsonl(self, tmp_path):
        projects_root = tmp_path / "projects"
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test-parse",
            sources=[{
                "id": "src.test",
                "file": "sources/test.pdf",
                "title": "Test",
                "source_kind": "BOOK",
            }],
        )
        # Mock marker to return known markdown
        mock_md = "# Chapter 1\nSome content.\n## Section A\nMore content.\n"
        with patch(
            "capability_commons.cli.ingest.parse.convert_pdf_to_markdown",
            return_value={"markdown": mock_md, "pages": [{"page": 1}]},
        ):
            run_parse(proj)

        assert proj.segments_file.exists()
        lines = proj.segments_file.read_text().strip().split("\n")
        assert len(lines) >= 2
        seg = SourceSegment.model_validate(orjson.loads(lines[0]))
        assert seg.source_id == "src.test"
