"""Tests for the heuristic intent classifier (retrieval P0-5)."""
from __future__ import annotations

import pytest

from capability_commons.domain.enums import RetrievalIntent
from capability_commons.retrieval.intent import infer_intent
from capability_commons.retrieval.service import RetrievalService
from capability_commons.schemas.retrieval import RetrievalRequest


@pytest.mark.parametrize(
    "query, expected",
    [
        # PLAN.md gold examples + ordinary how-to.
        ("How do I store water if the power is out?", RetrievalIntent.HOW_TO),
        ("Why is my rain barrel system not flowing?", RetrievalIntent.DEBUG_FAILURE),
        ("What should I learn before off-grid refrigeration?", RetrievalIntent.LEARN_PATH),
        ("Compare propane vs solar fridge for renters", RetrievalIntent.COMPARE_OPTIONS),
        ("Is bleach safe for treating drinking water?", RetrievalIntent.SAFETY_CHECK),
        ("Renter-safe food resilience", RetrievalIntent.LOCALIZE),
        ("What's new in the home solar guide?", RetrievalIntent.WHAT_CHANGED),
        ("Why does chlorine treatment work?", RetrievalIntent.WHY),
    ],
)
def test_infer_intent_examples(query: str, expected: RetrievalIntent):
    assert infer_intent(query) == expected


def test_empty_query_defaults_to_how_to():
    assert infer_intent("") == RetrievalIntent.HOW_TO
    assert infer_intent("   ") == RetrievalIntent.HOW_TO


def test_unrelated_query_defaults_to_how_to():
    # Pure noun phrase with no clear cue → still useful default.
    assert infer_intent("food storage containers") == RetrievalIntent.HOW_TO


def test_service_fills_missing_intent():
    req = RetrievalRequest(query="Why is my rain barrel not flowing?", intent=None)
    resolved = RetrievalService._with_resolved_intent(req)
    assert resolved.intent == RetrievalIntent.DEBUG_FAILURE


def test_service_preserves_explicit_intent():
    req = RetrievalRequest(query="anything", intent=RetrievalIntent.SAFETY_CHECK)
    resolved = RetrievalService._with_resolved_intent(req)
    assert resolved.intent == RetrievalIntent.SAFETY_CHECK
