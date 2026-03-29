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
