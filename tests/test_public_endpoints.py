"""Tests for public API endpoints."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import public


def test_list_public_objects_endpoint_exists():
    """GET /v1/public/objects endpoint must exist."""
    assert hasattr(public, "list_public_objects")
    sig = inspect.signature(public.list_public_objects)
    assert "session" in sig.parameters
