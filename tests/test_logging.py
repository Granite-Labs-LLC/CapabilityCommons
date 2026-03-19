"""Tests for logging middleware."""
from __future__ import annotations

import inspect

from capability_commons.api.logging_middleware import RequestLoggingMiddleware


def test_logging_middleware_exists():
    assert hasattr(RequestLoggingMiddleware, "__init__")
    sig = inspect.signature(RequestLoggingMiddleware.__init__)
    assert "app" in sig.parameters
