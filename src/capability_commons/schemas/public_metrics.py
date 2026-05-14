from __future__ import annotations

from pydantic import BaseModel


class PublicMetricsResponse(BaseModel):
    """Counts surfaced on the public status page (FE-STATUS-1)."""
    objects: int
    edges: int
    evidence_spans: int
    ingest_jobs: int
    last_ingest_at: str | None = None
