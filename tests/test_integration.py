from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from capability_commons.domain.enums import (
    COType,
    EdgeType,
    FacetType,
    LifecycleState,
    NodeKind,
    VisibilityType,
)
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.services.registry import RegistryService


@pytest.mark.asyncio
async def test_object_lifecycle(db_session, workspace):
    """Create object -> create version -> publish -> verify state."""
    service = RegistryService(db_session)

    req = CreateObjectRequest(
        workspace_id=workspace.id,
        slug="test-skill",
        type=COType.SKILL_GUIDE,
        canonical_title="Test Skill",
    )
    obj = await service.create_object(req)
    assert obj.lifecycle_state == LifecycleState.DRAFT

    ver_req = CreateVersionRequest(
        title="Test Skill v1",
        plain_language="A test skill.",
        markdown_body="# Test\nBody content.",
        structured_data={
            "performance_statement": "Do the test thing",
            "success_criteria": ["Passes"],
            "failure_modes": ["Fails"],
        },
    )
    version = await service.create_version(obj.id, ver_req)
    assert version.version_no == 1

    published_obj = await service.publish_version(obj.id, version.id)
    assert published_obj.lifecycle_state == LifecycleState.PUBLISHED
    assert published_obj.current_version_id == version.id


@pytest.mark.asyncio
async def test_edge_creation(db_session, workspace):
    """Create two objects and link them with an edge."""
    service = RegistryService(db_session)

    obj_a = await service.create_object(CreateObjectRequest(
        workspace_id=workspace.id, slug="node-a", type=COType.CONCEPT_NOTE, canonical_title="Node A",
    ))
    ver_a = await service.create_version(obj_a.id, CreateVersionRequest(
        title="Node A v1", plain_language="Node A.", markdown_body="Body A.",
        structured_data={"definition": "A concept."},
    ))

    obj_b = await service.create_object(CreateObjectRequest(
        workspace_id=workspace.id, slug="node-b", type=COType.CONCEPT_NOTE, canonical_title="Node B",
    ))
    ver_b = await service.create_version(obj_b.id, CreateVersionRequest(
        title="Node B v1", plain_language="Node B.", markdown_body="Body B.",
        structured_data={"definition": "Another concept."},
    ))

    edge = await service.create_edge(
        workspace_id=workspace.id,
        src_node_kind=NodeKind.OBJECT_VERSION,
        src_id=ver_a.id,
        edge_type=EdgeType.PREREQUISITE_FOR,
        dst_node_kind=NodeKind.OBJECT_VERSION,
        dst_id=ver_b.id,
    )
    assert edge.edge_type == EdgeType.PREREQUISITE_FOR


@pytest.mark.asyncio
async def test_facet_attachment(db_session, workspace):
    """Create object, attach facets, verify retrieval."""
    service = RegistryService(db_session)

    obj = await service.create_object(CreateObjectRequest(
        workspace_id=workspace.id, slug="faceted", type=COType.SKILL_GUIDE, canonical_title="Faceted",
    ))
    version = await service.create_version(obj.id, CreateVersionRequest(
        title="Faceted v1", plain_language="Test.", markdown_body="Body.",
        structured_data={
            "performance_statement": "Do it",
            "success_criteria": ["Done"],
            "failure_modes": ["Not done"],
        },
    ))

    await service.attach_facets(obj.id, version.id, [
        {"facet_type": FacetType.DOMAIN.value, "facet_value": "water"},
        {"facet_type": FacetType.AUDIENCE.value, "facet_value": "general"},
    ])

    refreshed = await service.get_version(version.id)
    facet_types = [f.facet_type for f in refreshed.facets]
    assert FacetType.DOMAIN in facet_types
    assert FacetType.AUDIENCE in facet_types
