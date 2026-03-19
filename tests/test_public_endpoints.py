"""Tests for public API endpoints."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import public


def test_list_public_objects_endpoint_exists():
    """GET /v1/public/objects endpoint must exist."""
    assert hasattr(public, "list_public_objects")
    sig = inspect.signature(public.list_public_objects)
    assert "session" in sig.parameters


def test_public_graph_endpoint_exists():
    """GET /v1/public/graph endpoint must exist."""
    assert hasattr(public, "public_graph")
    sig = inspect.signature(public.public_graph)
    assert "session" in sig.parameters


def test_graph_response_schema():
    """GraphResponse must have nodes and edges fields."""
    from capability_commons.schemas.graph import GraphResponse
    fields = GraphResponse.model_fields
    assert "nodes" in fields
    assert "edges" in fields
