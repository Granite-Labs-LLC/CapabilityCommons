"""Integration tests for the embedding pipeline: publish → outbox → index → embed."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from capability_commons.cli.worker import OutboxWorker
from capability_commons.config import get_settings
from capability_commons.db.models import ContentSegment, OutboxEvent
from capability_commons.domain.enums import COType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.search.indexer import VersionIndexer
from capability_commons.services.embedding import EmbeddingProvider, EmbeddingService
from capability_commons.services.registry import RegistryService


class _FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim
        self.calls = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[0.1] * self.dim for _ in texts]


@pytest.mark.asyncio
async def test_publish_creates_outbox_event(db_session, workspace):
    """Publishing a version should emit a version.published outbox event."""
    svc = RegistryService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-embed-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Embedding Test Object",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Embedding Test v1",
        plain_language="A test for the embedding pipeline.",
        markdown_body="# Embedding Test\n\nThis tests the full pipeline.",
        structured_data={"definition": "A test concept."},
    ))

    await svc.publish_version(obj.id, ver.id)

    # version.published events are recorded against the *object* aggregate
    # (aggregate_id == obj.id), not the version — consistent with both
    # RegistryService.publish_version and cli/seed.py's seed_graph(). The
    # version id lives in payload["version_id"], which is what the worker
    # actually reads. This was previously querying aggregate_id == ver.id,
    # which never matches — a test bug, not a product bug.
    result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "version.published",
            OutboxEvent.aggregate_id == obj.id,
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.payload["version_id"] == str(ver.id)
    assert event.payload["version_id"] == str(ver.id)


@pytest.mark.asyncio
async def test_reindex_creates_segments(db_session, workspace):
    """Indexing a published version should create content_segments rows."""
    svc = RegistryService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-seg-{uuid.uuid4().hex[:6]}",
        type=COType.SKILL_GUIDE,
        canonical_title="Segment Test",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Segment Test v1",
        plain_language="A skill for testing segment creation.",
        markdown_body="# Segment Test\n\nStep 1: Do the thing.\n\nStep 2: Verify.",
        structured_data={
            "performance_statement": "Test it",
            "learning_objectives": ["Test"],
            "steps_summary": ["Step 1"],
            "success_criteria": ["Passes"],
            "failure_modes": ["Fails"],
            "safety_boundary": "None",
            "teach_forward": {
                "three_minute_script": "Explain.",
                "ten_minute_outline": ["Intro"],
                "handout_points": ["Point"],
            },
        },
    ))
    await svc.publish_version(obj.id, ver.id)

    indexer = VersionIndexer(db_session)
    segments = await indexer.reindex_version(ver.id)

    assert len(segments) > 0

    result = await db_session.execute(
        select(ContentSegment).where(ContentSegment.context_object_version_id == ver.id)
    )
    db_segments = result.scalars().all()
    assert len(db_segments) == len(segments)
    for seg in db_segments:
        assert seg.text_content
        assert seg.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_embed_version_stores_vectors(db_session, workspace):
    """EmbeddingService.embed_version should store vectors on segments using a fake provider."""
    svc = RegistryService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-vec-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Vector Test",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Vector Test v1",
        plain_language="Testing embedding storage.",
        markdown_body="# Vector Test\n\nContent for embedding.",
        structured_data={"definition": "A vector test."},
    ))
    await svc.publish_version(obj.id, ver.id)

    indexer = VersionIndexer(db_session)
    await indexer.reindex_version(ver.id)

    embed_svc = EmbeddingService(db_session, provider=_FakeEmbeddingProvider())
    count = await embed_svc.embed_version(ver.id)

    assert count > 0

    result = await db_session.execute(
        select(ContentSegment).where(ContentSegment.context_object_version_id == ver.id)
    )
    for seg in result.scalars().all():
        assert seg.embedding is not None


@pytest.mark.asyncio
async def test_worker_leaves_failed_event_unprocessed_for_retry(db_session):
    """A handler exception (e.g. an invalid OPENAI_API_KEY) must not mark the
    outbox event processed. Regression test: this used to mark every event
    processed_at unconditionally, which permanently and silently dropped
    embeddings for any object indexed while the key was bad, with no way to
    recover them short of a bespoke backfill."""
    event = OutboxEvent(
        aggregate_type="context_object",
        aggregate_id=uuid.uuid4(),
        event_type="version.reindexed",
        payload={"version_id": str(uuid.uuid4())},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    worker = OutboxWorker(get_settings().database_url)

    async def _boom(session, ev):
        raise RuntimeError("simulated handler failure")

    worker._dispatch = _boom  # type: ignore[method-assign]

    try:
        succeeded = await worker._poll_batch()
    finally:
        await worker.stop()

    assert succeeded == 0

    result = await db_session.execute(
        select(OutboxEvent).where(OutboxEvent.id == event.id)
    )
    refreshed = result.scalar_one()
    assert refreshed.processed_at is None

    await db_session.delete(refreshed)
    await db_session.commit()
