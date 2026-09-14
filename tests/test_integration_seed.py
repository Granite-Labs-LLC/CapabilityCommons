"""Integration tests for cli/seed.py's seed_graph() against a real database."""

from __future__ import annotations

import uuid

import pytest
import yaml
from sqlalchemy import delete, select

from capability_commons.cli.seed import seed_graph
from capability_commons.config import get_settings
from capability_commons.db.models import ContextObject, EvidenceSource, EvidenceSpan, OutboxEvent
from capability_commons.domain.enums import EvidenceSourceKind, LifecycleState


def _node(slug: str, risk_band: str) -> dict:
    return {
        "slug": slug,
        "co_type": "skill_guide",
        "canonical_title": slug,
        "lifecycle_state": "published",
        "risk_band": risk_band,
        "stage": "household",
        "cost_band": "low",
        "difficulty": 2,
        "summary_short": "Test object.",
        "plain_language": "Test object.",
        "markdown_body": "## What this is\nTest object.",
        "structured_data": {"safety_boundary": "Test boundary."},
    }


@pytest.mark.asyncio
async def test_seed_graph_holds_high_risk_objects_for_review(db_session, tmp_path):
    """High-risk objects loaded as published must land in_review with no
    publish event -- the same rule PublishGate enforces on the API path --
    while low-risk objects still publish and get indexed."""
    suffix = uuid.uuid4().hex[:6]
    high, low = f"test-seed-high-{suffix}", f"test-seed-low-{suffix}"
    nodes_dir = tmp_path / "canonical" / "nodes"
    nodes_dir.mkdir(parents=True)
    for node in (_node(high, "high"), _node(low, "low")):
        (nodes_dir / f"{node['slug']}.yaml").write_text(yaml.safe_dump(node))

    try:
        await seed_graph(tmp_path, get_settings().database_url)

        result = await db_session.execute(select(ContextObject).where(ContextObject.slug.in_([high, low])))
        objs = {obj.slug: obj for obj in result.scalars()}
        assert objs[high].lifecycle_state == LifecycleState.IN_REVIEW
        assert objs[high].published_at is None
        assert objs[high].current_version_id is not None  # reviewers need the version
        assert objs[low].lifecycle_state == LifecycleState.PUBLISHED
        assert objs[low].published_at is not None

        events = await db_session.execute(
            select(OutboxEvent.aggregate_id).where(
                OutboxEvent.event_type == "version.published",
                OutboxEvent.aggregate_id.in_([objs[high].id, objs[low].id]),
            )
        )
        assert events.scalars().all() == [objs[low].id]
    finally:
        # seed_graph() writes into the real "capability-commons" workspace, not
        # a test-% one, so conftest's workspace cleanup doesn't cover these.
        test_object_ids = select(ContextObject.id).where(ContextObject.slug.in_([high, low]))
        await db_session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(test_object_ids)))
        await db_session.execute(delete(ContextObject).where(ContextObject.slug.in_([high, low])))
        await db_session.commit()


@pytest.mark.asyncio
async def test_seed_graph_uses_source_metadata(db_session, tmp_path):
    """Evidence sources take their title and kind from imports/sources.yaml
    (written by `ingest load`) instead of defaulting to BOOK and the bare id."""
    suffix = uuid.uuid4().hex[:6]
    slug, source_id = f"test-seed-source-{suffix}", f"src.test.{suffix}"
    node = _node(slug, "low")
    node["citations"] = [
        {"claim_id": "c1", "support": [{"source_id": source_id, "excerpt": "Test excerpt."}]},
        # The cite pass's "no support" placeholder must not become a span.
        {"claim_id": "c2", "support": [{"source_id": "NO_SUPPORT", "excerpt": ""}]},
    ]
    (tmp_path / "canonical" / "nodes").mkdir(parents=True)
    (tmp_path / "canonical" / "nodes" / f"{slug}.yaml").write_text(yaml.safe_dump(node))
    (tmp_path / "imports").mkdir()
    (tmp_path / "imports" / "sources.yaml").write_text(
        yaml.safe_dump([{"id": source_id, "title": "Test Source Title", "source_kind": "EXTERNAL_DOC"}])
    )

    try:
        await seed_graph(tmp_path, get_settings().database_url)

        result = await db_session.execute(select(EvidenceSource).where(EvidenceSource.external_id == source_id))
        source = result.scalar_one()
        assert source.title == "Test Source Title"
        assert source.source_kind == EvidenceSourceKind.EXTERNAL_DOC

        obj = (await db_session.execute(select(ContextObject).where(ContextObject.slug == slug))).scalar_one()
        spans = await db_session.execute(
            select(EvidenceSpan).where(EvidenceSpan.context_object_version_id == obj.current_version_id)
        )
        assert [span.source_id for span in spans.scalars()] == [source.id]
    finally:
        source_ids = select(EvidenceSource.id).where(EvidenceSource.external_id == source_id)
        object_ids = select(ContextObject.id).where(ContextObject.slug == slug)
        await db_session.execute(delete(EvidenceSpan).where(EvidenceSpan.source_id.in_(source_ids)))
        await db_session.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(object_ids)))
        await db_session.execute(delete(ContextObject).where(ContextObject.slug == slug))
        await db_session.execute(delete(EvidenceSource).where(EvidenceSource.external_id == source_id))
        await db_session.commit()
