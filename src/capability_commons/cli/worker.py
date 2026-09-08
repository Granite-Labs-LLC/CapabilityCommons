"""Outbox event consumer — polls for unprocessed events and dispatches handlers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.db.models import OutboxEvent

logger = logging.getLogger(__name__)

# Event type → handler function name
HANDLERS: dict[str, str] = {
    "version.published": "_handle_version_published",
    "version.reindexed": "_handle_version_reindexed",
}


class OutboxWorker:
    def __init__(self, db_url: str, poll_interval: float = 2.0) -> None:
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False)
        self.poll_interval = poll_interval
        self._running = True

    async def run(self) -> None:
        logger.info("Outbox worker started (poll_interval=%.1fs)", self.poll_interval)
        iteration = 0
        while self._running:
            processed = await self._poll_batch()
            iteration += 1
            if iteration % 100 == 0:
                async with self.session_factory() as session:
                    deleted = await self.cleanup_rate_limits(session)
                    if deleted > 0:
                        logger.info("Cleaned up %d expired rate limit records", deleted)
            if processed == 0:
                await asyncio.sleep(self.poll_interval)

    async def cleanup_rate_limits(self, session) -> int:
        """Delete rate limit records older than 1 hour."""
        from datetime import timedelta

        from capability_commons.db.models import RateLimitLog

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await session.execute(delete(RateLimitLog).where(RateLimitLog.window_start < cutoff))
        await session.commit()
        return result.rowcount or 0

    async def stop(self) -> None:
        self._running = False
        await self.engine.dispose()

    async def _poll_batch(self, batch_size: int = 50) -> int:
        # Plain scalar ids/types only — no ORM instances survive past this
        # block, so nothing here can later be expired by another event's
        # rollback (see the per-event session below for why that matters).
        async with self.session_factory() as session:
            result = await session.execute(
                select(OutboxEvent.id, OutboxEvent.event_type)
                .where(OutboxEvent.processed_at.is_(None))
                .order_by(OutboxEvent.id.asc())
                .limit(batch_size)
            )
            rows = result.all()

        if not rows:
            return 0

        succeeded = 0
        for event_id, event_type in rows:
            # One session/transaction per event, not one shared across the
            # whole batch. A handler failure that raises from a
            # session.flush() (e.g. StaleDataError) leaves that
            # transaction needing an explicit rollback, and rollback()
            # expires *every* ORM object still tracked in the session's
            # identity map — not just the one that failed. Plain attribute
            # access on an expired object under AsyncSession requires a
            # real DB round-trip, invalid outside an awaited context
            # (raises MissingGreenlet). With one shared session, that
            # blast radius reaches every other event already loaded into
            # this batch, and — since a permanently-failing event always
            # sorts first again on the next poll (skip_locked doesn't
            # exclude one's *own* worker on the next call, and it never
            # gets marked processed) — every event behind it would starve
            # forever, not just get delayed one cycle. A dedicated session
            # per event contains a failure to that event alone: nothing
            # else in the batch is ever at risk of touching an object
            # expired by someone else's rollback.
            #
            # Regression: found live during the 2026-09-08 FEMA ingestion —
            # a StaleDataError inside one handler crashed the whole worker
            # process (uncaught, escaping run()'s while loop), leaving a
            # growing backlog with nobody consuming it.
            async with self.session_factory() as session:
                event = (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.id == event_id, OutboxEvent.processed_at.is_(None))
                        .with_for_update(skip_locked=True)
                    )
                ).scalar_one_or_none()
                if event is None:
                    continue  # already processed or claimed by another worker

                try:
                    await self._dispatch(session, event)
                except Exception:
                    # Leave processed_at unset so this event is retried on a
                    # later poll instead of silently and permanently losing
                    # whatever the handler was supposed to do (e.g. an
                    # invalid/expired OPENAI_API_KEY should be retryable
                    # once fixed, not a permanent skip).
                    await session.rollback()
                    logger.exception(
                        "Failed to process event %d (%s) — leaving unprocessed for retry",
                        event_id,
                        event_type,
                    )
                    continue

                event.processed_at = datetime.now(timezone.utc)
                await session.commit()
                succeeded += 1

        logger.info("Processed %d/%d outbox events", succeeded, len(rows))
        return succeeded

    async def _dispatch(self, session, event: OutboxEvent) -> None:
        handler_name = HANDLERS.get(event.event_type)
        if handler_name is None:
            return  # No handler for this event type — mark processed and move on

        handler = getattr(self, handler_name)
        await handler(session, event)

    async def _handle_version_published(self, session, event: OutboxEvent) -> None:
        """Reindex the published version for search."""
        import uuid

        from capability_commons.search.indexer import VersionIndexer

        version_id = uuid.UUID(event.payload.get("version_id", str(event.aggregate_id)))
        indexer = VersionIndexer(session)
        segments = await indexer.reindex_version(version_id)
        logger.info("Reindexed version %s (%d segments)", version_id, len(segments))

    async def _handle_version_reindexed(self, session, event: OutboxEvent) -> None:
        """Generate embeddings for reindexed segments."""
        import uuid

        from capability_commons.config import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            logger.debug("No OPENAI_API_KEY configured, skipping embedding generation")
            return

        version_id = uuid.UUID(event.payload.get("version_id", str(event.aggregate_id)))
        from capability_commons.services.embedding import EmbeddingService

        embedding_svc = EmbeddingService(session)
        count = await embedding_svc.embed_version(version_id)
        logger.info("Generated embeddings for version %s (%d segments)", version_id, count)


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run the outbox event worker")
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--poll-interval", type=float, default=None)
    args = parser.parse_args()

    from capability_commons.config import get_settings

    settings = get_settings()

    db_url = args.db_url or settings.database_url
    poll_interval = args.poll_interval or settings.outbox_poll_interval_seconds

    worker = OutboxWorker(db_url, poll_interval)

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        asyncio.run(worker.stop())
        print("Worker stopped")


if __name__ == "__main__":
    main()
