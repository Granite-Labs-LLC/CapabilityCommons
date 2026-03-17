"""Tests that verify auth is wired into route handler signatures."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import edges, entities, evidence, objects, retrieval, reviews, search


def _has_workspace_param(func) -> bool:
    """Check if a route handler has a 'workspace' parameter."""
    sig = inspect.signature(func)
    return "workspace" in sig.parameters


def test_object_list_requires_workspace():
    assert _has_workspace_param(objects.list_objects)


def test_object_create_requires_workspace():
    assert _has_workspace_param(objects.create_object)


def test_entity_create_requires_workspace():
    assert _has_workspace_param(entities.create_entity)


def test_edge_create_requires_workspace():
    assert _has_workspace_param(edges.create_edge)


def test_evidence_create_source_requires_workspace():
    assert _has_workspace_param(evidence.create_source)


def test_review_submit_requires_workspace():
    assert _has_workspace_param(reviews.submit_review)


def test_contradiction_open_requires_workspace():
    assert _has_workspace_param(reviews.open_contradiction)


def test_search_requires_workspace():
    assert _has_workspace_param(search.search)


def test_retrieval_requires_workspace():
    assert _has_workspace_param(retrieval.retrieve_evidence_pack)


def test_public_routes_do_not_require_workspace():
    """Public routes should NOT require auth."""
    from capability_commons.api.routes import public
    assert not _has_workspace_param(public.public_object)
    assert not _has_workspace_param(public.public_module)
    assert not _has_workspace_param(public.public_path)
    assert not _has_workspace_param(public.public_bundle)
