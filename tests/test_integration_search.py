"""Integration tests for the search adapter: indexing, ranking, segment fetch."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from capability_commons.db.models import ContentSegment
from capability_commons.domain.enums import COType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
from capability_commons.search.indexer import VersionIndexer
from capability_commons.services.registry import RegistryService


def _skill_structured(statement: str = "Do it") -> dict:
    return {
        "performance_statement": statement,
        "learning_objectives": ["Learn"],
        "steps_summary": ["Step 1"],
        "success_criteria": ["Pass"],
        "failure_modes": ["Fail"],
        "safety_boundary": "None",
        "teach_forward": {
            "three_minute_script": "Explain.",
            "ten_minute_outline": ["Intro"],
            "handout_points": ["Point"],
        },
    }


async def _create_and_index(svc, indexer, workspace, slug_suffix, title, body, structured_data):
    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-srch-{slug_suffix}-{uuid.uuid4().hex[:6]}",
        type=COType.SKILL_GUIDE,
        canonical_title=title,
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title=title,
        plain_language=f"Plain language for {title}.",
        markdown_body=body,
        structured_data=structured_data,
    ))
    await svc.publish_version(obj.id, ver.id)
    await indexer.reindex_version(ver.id)
    return obj, ver


@pytest.mark.asyncio
async def test_search_returns_indexed_objects(db_session, workspace):
    """Search should find objects that have been indexed."""
    svc = RegistryService(db_session)
    indexer = VersionIndexer(db_session)
    search = PostgresSearchAdapter(db_session)

    obj, _ = await _create_and_index(
        svc, indexer, workspace, "findme", "Rainwater Harvesting Technique",
        "# Rainwater Harvesting\n\nCollect rainwater from rooftops using gutters and barrels.",
        _skill_structured("Harvest rainwater from rooftops"),
    )

    hits = await search.search(
        workspace_id=workspace.id,
        query="rainwater harvesting",
        filters={},
        top_k=10,
    )

    slugs = [h.slug for h in hits]
    assert obj.slug in slugs, f"Expected {obj.slug} in {slugs}"


@pytest.mark.asyncio
async def test_search_excludes_unpublished(db_session, workspace):
    """Search with only_published=True should exclude unpublished objects."""
    svc = RegistryService(db_session)
    search = PostgresSearchAdapter(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-srch-nopub-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Unpublished Sentinel Object",
    ))
    await svc.create_version(obj.id, CreateVersionRequest(
        title="Unpublished Sentinel",
        plain_language="Not published.",
        markdown_body="# Unpublished Sentinel",
        structured_data={"definition": "Not published."},
    ))

    hits = await search.search(
        workspace_id=workspace.id,
        query="unpublished sentinel",
        filters={},
        top_k=10,
    )
    slugs = [h.slug for h in hits]
    assert obj.slug not in slugs


@pytest.mark.asyncio
async def test_fetch_segments(db_session, workspace):
    """fetch_segments should return segments by their IDs."""
    svc = RegistryService(db_session)
    indexer = VersionIndexer(db_session)
    search = PostgresSearchAdapter(db_session)

    _, ver = await _create_and_index(
        svc, indexer, workspace, "fetchseg", "Fetch Segments Test",
        "# Fetch Test\n\nSome content for segment fetching.",
        _skill_structured("Fetch segments"),
    )

    result = await db_session.execute(
        select(ContentSegment.id).where(ContentSegment.context_object_version_id == ver.id)
    )
    seg_ids = [row[0] for row in result.all()]
    assert len(seg_ids) > 0

    fetched = await search.fetch_segments(seg_ids)
    assert len(fetched) == len(seg_ids)
    fetched_ids = {seg.id for seg in fetched}
    assert fetched_ids == set(seg_ids)
