from __future__ import annotations

from pydantic import BaseModel


class PublicMetricsResponse(BaseModel):
    """Counts surfaced on the public status page (FE-STATUS-1)."""
    objects: int
    edges: int
    evidence_spans: int
    ingest_jobs: int
    last_ingest_at: str | None = None


class PublicQualityMetricsResponse(BaseModel):
    """Answer-quality aggregates (METRICS-2). Anonymous; aggregates only."""
    retrieval_runs_total: int
    retrieval_runs_completed: int
    completion_rate: float
    avg_sufficiency_score: float
    avg_latency_ms: float
    unique_conversations: int
    followup_rate: float
    pct_answers_with_action_now: float
    pct_answers_with_2plus_citations: float
    feedback_by_action: dict[str, int]
