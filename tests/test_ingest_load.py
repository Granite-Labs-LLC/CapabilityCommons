"""Tests for extended seed.py with ingestion YAML support."""
from __future__ import annotations

import pytest

from capability_commons.cli.seed import (
    build_structured_data,
    resolve_co_type,
    resolve_requires,
)
from capability_commons.domain.enums import COType


class TestResolveCOType:
    def test_from_co_type_field(self):
        node = {"co_type": "PROJECT_BLUEPRINT"}
        assert resolve_co_type(node) == COType.PROJECT_BLUEPRINT

    def test_from_type_field_fallback(self):
        node = {"type": "skill"}
        assert resolve_co_type(node) == COType.SKILL_GUIDE

    def test_co_type_takes_precedence(self):
        node = {"co_type": "MODULE", "type": "concept"}
        assert resolve_co_type(node) == COType.MODULE

    def test_unknown_type_raises(self):
        with pytest.raises((KeyError, ValueError)):
            resolve_co_type({"type": "nonexistent"})


class TestResolveRequires:
    def test_flat_list(self):
        node = {"id": "water.test", "requires": ["a.b", "c.d"]}
        triples = resolve_requires(node)
        assert triples == [
            ("water.test", "a.b", {}),
            ("water.test", "c.d", {}),
        ]

    def test_grouped_format_preserves_mode(self):
        node = {
            "id": "water.test",
            "requires": [{"mode": "all_of", "ids": ["a.b", "c.d"]}],
        }
        triples = resolve_requires(node)
        assert ("water.test", "a.b", {"group_mode": "all_of"}) in triples
        assert ("water.test", "c.d", {"group_mode": "all_of"}) in triples

    def test_empty_requires(self):
        node = {"id": "test", "requires": []}
        assert resolve_requires(node) == []

    def test_no_requires_field(self):
        node = {"id": "test"}
        assert resolve_requires(node) == []


class TestBuildStructuredData:
    def test_markdown_body_used_when_present(self):
        node = {
            "markdown_body": "# Real content\nWith paragraphs.",
            "summary": "Short summary",
        }
        body = node.get("markdown_body") or node.get("summary", "")
        assert body == "# Real content\nWith paragraphs."

    def test_fallback_to_summary(self):
        node = {"summary": "Short summary"}
        body = node.get("markdown_body") or node.get("summary", "")
        assert body == "Short summary"

    def test_structured_data_merges_with_payload(self):
        node = {
            "payload": {"tools": ["hammer"]},
            "structured_data": {"goal": "build a thing"},
        }
        sd = build_structured_data(node)
        assert sd["tools"] == ["hammer"]
        assert sd["goal"] == "build a thing"

    def test_bundle_overrides_stored(self):
        node = {
            "bundle_overrides": {"hook": "Why this matters"},
        }
        sd = build_structured_data(node)
        assert sd["_bundle"]["hook"] == "Why this matters"

    def test_summary_long_not_in_structured_data(self):
        """summary_long goes to the ORM column, not structured_data."""
        node = {"summary_long": "A very long summary..."}
        sd = build_structured_data(node)
        assert "summary_long" not in sd
