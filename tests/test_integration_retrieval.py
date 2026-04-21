"""Integration tests for the retrieval service: plan → search → graph → evidence pack."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from capability_commons.db.models import RetrievalRun
from capability_commons.domain.enums import COType, EdgeType, NodeKind, RetrievalIntent
from capability_commons.retrieval.service import RetrievalService
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.schemas.retrieval import RetrievalRequest
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


async def _seed_and_index(svc, indexer, workspace):
    concept_obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-ret-concept-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Water Safety Basics",
    ))
    concept_ver = await svc.create_version(concept_obj.id, CreateVersionRequest(
        title="Water Safety Basics",
        plain_language="Understanding safe drinking water sources and treatment methods.",
        markdown_body="# Water Safety\n\nTreatment methods include boiling, filtration, and chemical disinfection.",
        structured_data={"definition": "Core principles of household water safety."},
    ))

    skill_obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-ret-skill-{uuid.uuid4().hex[:6]}",
        type=COType.SKILL_GUIDE,
        canonical_title="Boil Water for Drinking",
    ))
    skill_ver = await svc.create_version(skill_obj.id, CreateVersionRequest(
        title="Boil Water for Drinking",
        plain_language="How to make water safe by bringing it to a rolling boil.",
        markdown_body="# Boiling Water\n\nBring water to a rolling boil for at least one minute. At altitude, boil for three minutes.",
        structured_data=_skill_structured("Boil water to make it safe for drinking"),
    ))

    await svc.publish_version(concept_obj.id, concept_ver.id)
    await svc.publish_version(skill_obj.id, skill_ver.id)

    await svc.create_edge(
        workspace_id=workspace.id,
        src_node_kind=NodeKind.OBJECT_VERSION, src_id=concept_ver.id,
        edge_type=EdgeType.PREREQUISITE_FOR,
        dst_node_kind=NodeKind.OBJECT_VERSION, dst_id=skill_ver.id,
    )

    await indexer.reindex_version(concept_ver.id)
    await indexer.reindex_version(skill_ver.id)

    return concept_obj, concept_ver, skill_obj, skill_ver


@pytest.mark.asyncio
async def test_execute_plan_returns_evidence_pack(db_session, workspace):
    """execute_plan should return an evidence pack with at least one evidence node."""
    svc = RegistryService(db_session)
    indexer = VersionIndexer(db_session)

    concept_obj, _, skill_obj, _ = await _seed_and_index(svc, indexer, workspace)

    retrieval = RetrievalService(db_session)

    request = RetrievalRequest(
        workspace_id=workspace.id,
        query="how to make water safe to drink",
        intent=RetrievalIntent.HOW_TO,
    )

    pack = await retrieval.execute_plan(request)

    assert pack is not None
    assert len(pack.evidence) > 0

    hit_slugs = [h.slug for h in pack.evidence]
    found = any(concept_obj.slug in s or skill_obj.slug in s for s in hit_slugs)
    assert found, f"Expected seeded objects in evidence, got: {hit_slugs}"


@pytest.mark.asyncio
async def test_retrieval_run_persisted(db_session, workspace):
    """execute_plan should persist a RetrievalRun record."""
    svc = RegistryService(db_session)
    indexer = VersionIndexer(db_session)
    await _seed_and_index(svc, indexer, workspace)

    retrieval = RetrievalService(db_session)

    request = RetrievalRequest(
        workspace_id=workspace.id,
        query="boiling water treatment",
        intent=RetrievalIntent.HOW_TO,
    )

    await retrieval.execute_plan(request)

    result = await db_session.execute(
        select(RetrievalRun).where(RetrievalRun.workspace_id == workspace.id)
    )
    runs = result.scalars().all()
    assert len(runs) > 0
    run = runs[-1]
    assert run.sufficiency_score is not None
