"""Outbox event consumer — polls for unprocessed events and dispatches handlers."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
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
        while self._running:
            processed = await self._poll_batch()
            if processed == 0:
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        await self.engine.dispose()

    async def _poll_batch(self, batch_size: int = 50) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed_at.is_(None))
                .order_by(OutboxEvent.id.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            events = list(result.scalars().all())

            if not events:
                return 0

            for event in events:
                try:
                    await self._dispatch(session, event)
                except Exception:
                    logger.exception("Failed to process event %d (%s)", event.id, event.event_type)

                event.processed_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info("Processed %d outbox events", len(events))
            return len(events)

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
