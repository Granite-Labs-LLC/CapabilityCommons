"""Tests that workspace_id is optional on public-facing request schemas."""
from __future__ import annotations

from capability_commons.schemas.search import SearchRequest
from capability_commons.schemas.retrieval import RetrievalRequest


def test_search_request_workspace_id_optional():
    req = SearchRequest(query="test water purification")
    assert req.workspace_id is None


def test_retrieval_request_workspace_id_optional():
    req = RetrievalRequest(query="how to purify water", intent="how_to")
    assert req.workspace_id is None
