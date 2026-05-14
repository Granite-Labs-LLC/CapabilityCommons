"""Observability metrics for ingest quality and public answer quality.

Provides aggregate statistics queryable via the /v1/metrics API.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import (
    ContentSegment,
    ContextObject,
    ContextObjectVersion,
    ContradictionCase,
    ConversationTurn,
    EvidenceSpan,
    Feedback,
    RetrievalRun,
    ReviewRecord,
)
from capability_commons.domain.enums import FeedbackAction
from capability_commons.domain.enums import (
    ContradictionStatus,
    LifecycleState,
    RetrievalRunStatus,
    ReviewOutcome,
    ValidityStatus,
)


class MetricsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ingest_quality(self) -> dict[str, Any]:
        """Aggregate ingest quality metrics."""
        # Total objects by lifecycle state
        lifecycle_counts = {}
        rows = await self.session.execute(
            select(ContextObject.lifecycle_state, func.count())
            .group_by(ContextObject.lifecycle_state)
        )
        for state, count in rows:
            lifecycle_counts[state.value if hasattr(state, "value") else str(state)] = count

        # Total versions and validity breakdown
        validity_counts = {}
        rows = await self.session.execute(
            select(ContextObjectVersion.validity_status, func.count())
            .group_by(ContextObjectVersion.validity_status)
        )
        for status, count in rows:
            validity_counts[status.value if hasattr(status, "value") else str(status)] = count

        # Evidence spans total
        evidence_count = await self.session.scalar(
            select(func.count()).select_from(EvidenceSpan)
        ) or 0

        # Content segments total and with embeddings
        segment_total = await self.session.scalar(
            select(func.count()).select_from(ContentSegment)
        ) or 0
        segments_with_embedding = await self.session.scalar(
            select(func.count()).where(ContentSegment.embedding.isnot(None))
        ) or 0

        # Reviews breakdown
        review_counts = {}
        rows = await self.session.execute(
            select(ReviewRecord.outcome, func.count())
            .group_by(ReviewRecord.outcome)
        )
        for outcome, count in rows:
            review_counts[outcome.value if hasattr(outcome, "value") else str(outcome)] = count

        # Open contradictions
        open_contradictions = await self.session.scalar(
            select(func.count()).where(
                ContradictionCase.status.in_([
                    ContradictionStatus.OPEN,
                    ContradictionStatus.TRIAGED,
                ])
            )
        ) or 0

        return {
            "objects_by_lifecycle": lifecycle_counts,
            "versions_by_validity": validity_counts,
            "evidence_spans": evidence_count,
            "content_segments_total": segment_total,
            "content_segments_embedded": segments_with_embedding,
            "embedding_coverage": round(segments_with_embedding / max(segment_total, 1), 3),
            "reviews_by_outcome": review_counts,
            "open_contradictions": open_contradictions,
        }

    async def answer_quality(self) -> dict[str, Any]:
        """Aggregate public answer quality metrics."""
        # Total retrieval runs
        total_runs = await self.session.scalar(
            select(func.count()).select_from(RetrievalRun)
        ) or 0

        # Completed runs
        completed_runs = await self.session.scalar(
            select(func.count()).where(
                RetrievalRun.status == RetrievalRunStatus.COMPLETED
            )
        ) or 0

        # Average sufficiency score
        avg_sufficiency = await self.session.scalar(
            select(func.avg(RetrievalRun.sufficiency_score)).where(
                RetrievalRun.status == RetrievalRunStatus.COMPLETED
            )
        )

        # Conversation turns total
        conversation_turns = await self.session.scalar(
            select(func.count()).select_from(ConversationTurn)
        ) or 0

        # Unique conversations
        unique_conversations = await self.session.scalar(
            select(func.count(func.distinct(ConversationTurn.conversation_id)))
        ) or 0

        # METRICS-2: latency (time-to-first-answer) on completed runs.
        latency_ms_avg = await self.session.scalar(
            select(
                func.avg(
                    func.extract("epoch", RetrievalRun.completed_at - RetrievalRun.created_at) * 1000
                )
            ).where(
                RetrievalRun.status == RetrievalRunStatus.COMPLETED,
                RetrievalRun.completed_at.isnot(None),
            )
        )

        # METRICS-2: result_summary JSON inspection for action_now /
        # citations grounded count. We use Postgres JSON operators so this
        # stays a single round trip.
        with_action_now = await self.session.scalar(
            select(func.count()).where(
                RetrievalRun.status == RetrievalRunStatus.COMPLETED,
                RetrievalRun.result_summary["action_now"].astext != "null",
                RetrievalRun.result_summary["action_now"].astext != "",
            )
        ) or 0
        with_2plus_citations = await self.session.scalar(
            select(func.count()).where(
                RetrievalRun.status == RetrievalRunStatus.COMPLETED,
                func.jsonb_array_length(RetrievalRun.result_summary["citations"]) >= 2,
            )
        ) or 0

        # METRICS-2: followup rate — count conversations that have >1 turn.
        followup_conversations = await self.session.scalar(
            select(func.count()).select_from(
                select(ConversationTurn.conversation_id)
                .group_by(ConversationTurn.conversation_id)
                .having(func.count(ConversationTurn.id) > 1)
                .subquery()
            )
        ) or 0
        followup_rate = (
            round(followup_conversations / unique_conversations, 3)
            if unique_conversations else 0.0
        )

        # METRICS-2: feedback summary by action.
        feedback_counts: dict[str, int] = {}
        rows = await self.session.execute(
            select(Feedback.action, func.count()).group_by(Feedback.action)
        )
        for action, count in rows:
            key = action.value if hasattr(action, "value") else str(action)
            feedback_counts[key] = count

        return {
            "retrieval_runs_total": total_runs,
            "retrieval_runs_completed": completed_runs,
            "completion_rate": round(completed_runs / max(total_runs, 1), 3),
            "avg_sufficiency_score": round(float(avg_sufficiency or 0), 3),
            "avg_latency_ms": round(float(latency_ms_avg or 0), 1),
            "conversation_turns_total": conversation_turns,
            "unique_conversations": unique_conversations,
            "followup_conversations": followup_conversations,
            "followup_rate": followup_rate,
            "pct_answers_with_action_now": round(with_action_now / max(completed_runs, 1), 3),
            "pct_answers_with_2plus_citations": round(with_2plus_citations / max(completed_runs, 1), 3),
            "feedback_by_action": feedback_counts,
        }

    async def summary(self) -> dict[str, Any]:
        """Combined metrics summary."""
        ingest = await self.ingest_quality()
        answer = await self.answer_quality()
        return {
            "ingest": ingest,
            "answer": answer,
        }
