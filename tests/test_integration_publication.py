"""Integration tests for the publication service: public objects, graph, render."""
from __future__ import annotations

import uuid

import pytest

from capability_commons.domain.enums import COType, EdgeType, NodeKind
from capability_commons.publication.service import PublicationService
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
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


async def _create_published_object(svc, workspace, slug_suffix, obj_type, title, body, structured_data):
    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-pub-{slug_suffix}-{uuid.uuid4().hex[:6]}",
        type=obj_type,
        canonical_title=title,
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title=title,
        plain_language=f"Plain language for {title}.",
        markdown_body=body,
        structured_data=structured_data,
    ))
    await svc.publish_version(obj.id, ver.id)
    return obj, ver


@pytest.mark.asyncio
async def test_list_published_objects(db_session, workspace):
    """list_published_objects returns only published objects."""
    svc = RegistryService(db_session)
    pub = PublicationService(db_session)

    obj1, _ = await _create_published_object(
        svc, workspace, "listed", COType.CONCEPT_NOTE, "Listed Concept",
        "# Listed\nBody.", {"definition": "A listed concept."},
    )

    draft = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-pub-draft-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Draft Object",
    ))
    await svc.create_version(draft.id, CreateVersionRequest(
        title="Draft v1", plain_language="Draft.", markdown_body="# Draft",
        structured_data={"definition": "Draft."},
    ))

    objects = await pub.list_published_objects()
    slugs = [o.slug for o in objects]

    assert obj1.slug in slugs
    assert draft.slug not in slugs


@pytest.mark.asyncio
async def test_build_graph_data(db_session, workspace):
    """build_graph_data returns nodes and edges for published objects."""
    svc = RegistryService(db_session)
    pub = PublicationService(db_session)

    obj_a, ver_a = await _create_published_object(
        svc, workspace, "graph-a", COType.CONCEPT_NOTE, "Graph Node A",
        "# Node A", {"definition": "Node A."},
    )
    obj_b, ver_b = await _create_published_object(
        svc, workspace, "graph-b", COType.SKILL_GUIDE, "Graph Node B",
        "# Node B", _skill_structured("Do B"),
    )

    await svc.create_edge(
        workspace_id=workspace.id,
        src_node_kind=NodeKind.OBJECT_VERSION, src_id=ver_a.id,
        edge_type=EdgeType.PREREQUISITE_FOR,
        dst_node_kind=NodeKind.OBJECT_VERSION, dst_id=ver_b.id,
    )

    graph = await pub.build_graph_data()

    node_slugs = [n.slug for n in graph.nodes]
    assert obj_a.slug in node_slugs
    assert obj_b.slug in node_slugs
    assert len(graph.edges) > 0


@pytest.mark.asyncio
async def test_render_public_object(db_session, workspace):
    """render_public_object returns full object with structured data."""
    svc = RegistryService(db_session)
    pub = PublicationService(db_session)

    obj, _ = await _create_published_object(
        svc, workspace, "render", COType.CONCEPT_NOTE, "Rendered Concept",
        "# Rendered\n\nFull body content for rendering test.",
        {"definition": "A rendered concept.", "key_questions": ["What?"]},
    )

    rendered = await pub.render_public_object(obj.slug)

    assert rendered.slug == obj.slug
    assert rendered.title == "Rendered Concept"
    assert rendered.structured_data is not None
    assert "definition" in rendered.structured_data


@pytest.mark.asyncio
async def test_unpublished_not_in_public(db_session, workspace):
    """Unpublished objects should not appear in any public method."""
    svc = RegistryService(db_session)
    pub = PublicationService(db_session)

    draft = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-pub-hidden-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Hidden Draft",
    ))
    await svc.create_version(draft.id, CreateVersionRequest(
        title="Hidden v1", plain_language="Hidden.", markdown_body="# Hidden",
        structured_data={"definition": "Hidden."},
    ))

    objects = await pub.list_published_objects()
    graph = await pub.build_graph_data()

    assert draft.slug not in [o.slug for o in objects]
    assert draft.slug not in [n.slug for n in graph.nodes]
