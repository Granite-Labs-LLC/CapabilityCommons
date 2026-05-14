"""Tests for the eval harness scoring logic (EVAL-1)."""
from __future__ import annotations

from capability_commons.cli.eval import GoldEntry, QueryResult, _render_report


def _result(**overrides) -> QueryResult:
    defaults = dict(
        entry=GoldEntry(query="x", expects_any=["a"]),
        ask_ok=True,
        ask_intent_match=None,
        ask_has_action_now=True,
        ask_citation_count=2,
        ask_top_slugs=["a"],
        search_ok=True,
        search_top_slugs=["a", "b"],
        error=None,
    )
    defaults.update(overrides)
    return QueryResult(**defaults)


def test_passes_when_any_hit_and_citations_meet_floor():
    r = _result()
    assert r.expects_any_hit is True
    assert r.expects_all_hit is True
    assert r.passed is True


def test_fails_when_expects_any_misses():
    r = _result(search_top_slugs=["x", "y"])
    assert r.expects_any_hit is False
    assert r.passed is False


def test_fails_when_below_min_citations():
    r = _result(ask_citation_count=1)
    assert r.passed is False


def test_fails_on_intent_mismatch_only_when_specified():
    r = _result(
        entry=GoldEntry(query="x", intent="how_to", expects_any=["a"]),
        ask_intent_match=False,
    )
    # intent_match is informational in `passed`; we surface it in the
    # failure block. The hard predicate stays: top-N + citations.
    # If we want intent to gate passing later, that becomes a follow-on.
    assert r.passed is True


def test_expects_all_must_be_full():
    r = _result(
        entry=GoldEntry(query="x", expects_all=["a", "z"], expects_any=[]),
        search_top_slugs=["a", "b"],
    )
    assert r.expects_all_hit is False
    assert r.passed is False


def test_render_report_has_summary_and_table():
    results = [
        _result(),
        _result(
            entry=GoldEntry(query="bad query", expects_any=["missing"]),
            search_top_slugs=["other"],
        ),
    ]
    md = _render_report(results, api_base="http://api.example")
    assert "Capability Commons retrieval eval" in md
    assert "Passed: 1 / 2" in md
    assert "## Failures" in md
    assert "bad query" in md
