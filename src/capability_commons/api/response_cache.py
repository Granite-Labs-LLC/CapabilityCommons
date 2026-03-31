"""In-memory TTL cache for public search and ask responses.

Uses a simple dict with timestamp-based expiry. Suitable for single-process
deployments; swap for Redis-backed cache in production clusters.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class ResponseCache:
    """TTL-based in-memory response cache."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: dict[str, tuple[float, Any]] = {}

    def _make_key(self, prefix: str, params: dict[str, Any]) -> str:
        """Create a deterministic cache key from prefix and parameters."""
        normalized = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"

    def get(self, prefix: str, params: dict[str, Any]) -> Any | None:
        """Retrieve a cached response, or None if expired/missing."""
        key = self._make_key(prefix, params)
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None
        return value

    def set(self, prefix: str, params: dict[str, Any], value: Any) -> None:
        """Store a response in the cache."""
        if len(self._cache) >= self.max_entries:
            self._evict_expired()
        if len(self._cache) >= self.max_entries:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        key = self._make_key(prefix, params)
        self._cache[key] = (time.monotonic(), value)

    def invalidate(self, prefix: str | None = None) -> int:
        """Invalidate entries. If prefix given, only those; else all."""
        if prefix is None:
            count = len(self._cache)
            self._cache.clear()
            return count
        to_remove = [k for k in self._cache if k.startswith(f"{prefix}:")]
        for k in to_remove:
            del self._cache[k]
        return len(to_remove)

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        now = time.monotonic()
        expired = [k for k, (ts, _) in self._cache.items() if now - ts > self.ttl_seconds]
        for k in expired:
            del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)


# Singleton cache instance used by routes
_cache: ResponseCache | None = None


def get_response_cache() -> ResponseCache:
    """Get or create the global response cache."""
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache
