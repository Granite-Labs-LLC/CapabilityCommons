# Testing & Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the full CapabilityCommons stack with integration tests for every untested subsystem plus API smoke tests.

**Architecture:** Five new test files using the existing `db_session` + `workspace` fixtures from `tests/conftest.py`. Integration tests run against real Postgres. Smoke tests use `TestClient`. CI workflow updated to run all integration tests.

**Tech Stack:** pytest, pytest-asyncio, SQLAlchemy 2 async, FastAPI TestClient, unittest.mock

---

## File Structure

| File | Responsibility |
|------|---------------|
| `tests/test_integration_embedding.py` | Publish → outbox → worker → segments → embeddings pipeline |
| `tests/test_integration_retrieval.py` | Plan → search → graph expand → evidence pack assembly |
| `tests/test_integration_publication.py` | Public objects, graph data, bundles |
| `tests/test_integration_search.py` | Search indexing, ranking, facet filtering |
| `tests/test_smoke_api.py` | Endpoint wiring for all 13 route modules |
| `.github/workflows/ci.yml` | Update integration job to run all `test_integration*.py` files |

---

### Task 1: Embedding Pipeline Integration Test

**Files:**
- Create: `tests/test_integration_embedding.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for the embedding pipeline: publish → outbox → index → embed."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text

from capability_commons.db.models import ContentSegment, OutboxEvent
from capability_commons.domain.enums import COType, LifecycleState
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.search.indexer import VersionIndexer
from capability_commons.services.embedding import EmbeddingService
from capability_commons.services.registry import RegistryService


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

    result = await db_session.execute(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "version.published",
            OutboxEvent.aggregate_id == ver.id,
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None, "Expected version.published outbox event"
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
        markdown_body="# Segment Test\n\nStep 1: Do the thing.\n\nStep 2: Verify the thing.",
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

    assert len(segments) > 0, "Expected at least one content segment"

    result = await db_session.execute(
        select(ContentSegment).where(ContentSegment.context_object_version_id == ver.id)
    )
    db_segments = result.scalars().all()
    assert len(db_segments) == len(segments)
    for seg in db_segments:
        assert seg.text_content, "Segment should have text content"
        assert seg.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_embed_version_stores_vectors(db_session, workspace):
    """EmbeddingService.embed_version should store vectors on segments (mocked OpenAI)."""
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

    fake_embedding = [0.1] * 1536

    with patch(
        "capability_commons.services.embedding.EmbeddingService._get_embeddings",
        new_callable=AsyncMock,
        return_value=[fake_embedding],
    ):
        embed_svc = EmbeddingService(db_session)
        count = await embed_svc.embed_version(ver.id)

    assert count > 0, "Expected at least one segment to be embedded"

    result = await db_session.execute(
        select(ContentSegment).where(ContentSegment.context_object_version_id == ver.id)
    )
    for seg in result.scalars().all():
        assert seg.embedding is not None, "Segment should have an embedding vector"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_integration_embedding.py -v`
Expected: 3 tests PASS (requires live Postgres with migrations applied)

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_embedding.py
git commit -m "test: add embedding pipeline integration tests"
```

---

### Task 2: Publication Service Integration Test

**Files:**
- Create: `tests/test_integration_publication.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for the publication service: public objects, graph, bundles."""
from __future__ import annotations

import uuid

import pytest

from capability_commons.domain.enums import COType, EdgeType, NodeKind
from capability_commons.publication.service import PublicationService
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.services.registry import RegistryService


async def _create_published_object(svc, workspace, slug_suffix, obj_type, title, body, structured_data):
    """Helper to create and publish an object in one call."""
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

    # Create an unpublished (draft) object
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

    assert obj1.slug in slugs, "Published object should appear"
    assert draft.slug not in slugs, "Draft object should not appear"


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
        "# Node B", {
            "performance_statement": "Do B", "learning_objectives": ["B"],
            "steps_summary": ["B1"], "success_criteria": ["Done"],
            "failure_modes": ["Fail"], "safety_boundary": "None",
            "teach_forward": {"three_minute_script": "B", "ten_minute_outline": ["B"], "handout_points": ["B"]},
        },
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

    assert len(graph.edges) > 0, "Expected at least one edge in graph"


@pytest.mark.asyncio
async def test_render_public_object(db_session, workspace):
    """render_public_object returns full object with structured data."""
    svc = RegistryService(db_session)
    pub = PublicationService(db_session)

    obj, ver = await _create_published_object(
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_integration_publication.py -v`
Expected: 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_publication.py
git commit -m "test: add publication service integration tests"
```

---

### Task 3: Search Adapter Integration Test

**Files:**
- Create: `tests/test_integration_search.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for the search adapter: indexing, ranking, facet filtering."""
from __future__ import annotations

import uuid

import pytest

from capability_commons.domain.enums import COType, FacetType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
from capability_commons.search.indexer import VersionIndexer
from capability_commons.services.registry import RegistryService


async def _create_and_index(svc, indexer, workspace, slug_suffix, title, body, structured_data, facets=None):
    """Helper: create, publish, index an object. Optionally attach facets."""
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
    if facets:
        await svc.attach_facets(obj.id, ver.id, facets)
    await svc.publish_version(obj.id, ver.id)
    await indexer.reindex_version(ver.id)
    return obj, ver


def _skill_structured(statement="Do it"):
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


@pytest.mark.asyncio
async def test_search_returns_indexed_objects(db_session, workspace):
    """Search should find objects that have been indexed."""
    svc = RegistryService(db_session)
    indexer = VersionIndexer(db_session)
    search = PostgresSearchAdapter(db_session)

    await _create_and_index(
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
    assert any("findme" in s for s in slugs), f"Expected to find 'findme' object in results: {slugs}"


@pytest.mark.asyncio
async def test_search_excludes_unindexed(db_session, workspace):
    """Objects that are not indexed should not appear in search results."""
    svc = RegistryService(db_session)
    search = PostgresSearchAdapter(db_session)

    # Create and publish but do NOT index
    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-srch-noindex-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Unindexed Object",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Unindexed", plain_language="Not indexed.", markdown_body="# Unindexed",
        structured_data={"definition": "Not indexed."},
    ))
    await svc.publish_version(obj.id, ver.id)

    hits = await search.search(
        workspace_id=workspace.id,
        query="unindexed object",
        filters={},
        top_k=10,
    )
    slugs = [h.slug for h in hits]
    assert obj.slug not in slugs, "Unindexed object should not appear in search"


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

    from sqlalchemy import select
    from capability_commons.db.models import ContentSegment

    result = await db_session.execute(
        select(ContentSegment.id).where(ContentSegment.context_object_version_id == ver.id)
    )
    seg_ids = [row[0] for row in result.all()]
    assert len(seg_ids) > 0, "Should have segments to fetch"

    fetched = await search.fetch_segments(seg_ids)
    assert len(fetched) == len(seg_ids)
    for seg in fetched:
        assert seg.id in seg_ids
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_integration_search.py -v`
Expected: 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_search.py
git commit -m "test: add search adapter integration tests"
```

---

### Task 4: Retrieval Service Integration Test

**Files:**
- Create: `tests/test_integration_retrieval.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for the retrieval service: plan → search → graph → evidence pack."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from capability_commons.domain.enums import COType, EdgeType, NodeKind, RetrievalIntent
from capability_commons.retrieval.service import RetrievalService
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.schemas.retrieval import RetrievalRequest
from capability_commons.search.indexer import VersionIndexer
from capability_commons.services.registry import RegistryService


def _skill_structured(statement="Do it"):
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
    """Create a small graph: concept → skill → project, all published and indexed."""
    concept_obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-ret-concept-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Water Safety Basics",
    ))
    concept_ver = await svc.create_version(concept_obj.id, CreateVersionRequest(
        title="Water Safety Basics",
        plain_language="Understanding safe drinking water sources and treatment methods.",
        markdown_body="# Water Safety\n\nSafe water is essential. Treatment methods include boiling, filtration, and chemical disinfection.",
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

    # Publish both
    await svc.publish_version(concept_obj.id, concept_ver.id)
    await svc.publish_version(skill_obj.id, skill_ver.id)

    # Create prerequisite edge: concept → skill
    await svc.create_edge(
        workspace_id=workspace.id,
        src_node_kind=NodeKind.OBJECT_VERSION, src_id=concept_ver.id,
        edge_type=EdgeType.PREREQUISITE_FOR,
        dst_node_kind=NodeKind.OBJECT_VERSION, dst_id=skill_ver.id,
    )

    # Index both
    await indexer.reindex_version(concept_ver.id)
    await indexer.reindex_version(skill_ver.id)

    return concept_obj, concept_ver, skill_obj, skill_ver


@pytest.mark.asyncio
async def test_execute_plan_returns_evidence_pack(db_session, workspace):
    """execute_plan should return an evidence pack with search results."""
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
    assert len(pack.hits) > 0, "Expected at least one hit in evidence pack"

    hit_slugs = [h.slug for h in pack.hits]
    # At least one of our seeded objects should appear
    found = any(concept_obj.slug in s or skill_obj.slug in s for s in hit_slugs)
    assert found, f"Expected seeded objects in hits, got: {hit_slugs}"


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

    pack = await retrieval.execute_plan(request)

    from sqlalchemy import select
    from capability_commons.db.models import RetrievalRun

    result = await db_session.execute(
        select(RetrievalRun).where(RetrievalRun.workspace_id == workspace.id)
    )
    runs = result.scalars().all()
    assert len(runs) > 0, "Expected at least one RetrievalRun"
    run = runs[-1]
    assert run.status in ("completed", "budget_exhausted")
    assert run.sufficiency_score is not None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_integration_retrieval.py -v`
Expected: 2 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration_retrieval.py
git commit -m "test: add retrieval service integration tests"
```

---

### Task 5: API Smoke Tests

**Files:**
- Create: `tests/test_smoke_api.py`

- [ ] **Step 1: Write the test file**

```python
"""Smoke tests: verify every route module is wired and responds correctly."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Health ──────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_detailed(client):
    r = client.get("/health/detailed")
    assert r.status_code == 200
    data = r.json()
    assert "database" in data
    assert "migrations" in data


# ── Public (no auth) ────────────────────────────────────────

def test_public_objects(client):
    r = client.get("/v1/public/objects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_public_graph(client):
    r = client.get("/v1/public/graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


# ── Search (no auth) ────────────────────────────────────────

def test_search(client):
    r = client.post("/v1/search", json={"query": "water"})
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert "hits" in data


# ── Ask (no auth) ───────────────────────────────────────────

def test_ask(client):
    r = client.post("/v1/public/ask", json={"query": "how to purify water"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data


# ── Feedback (no auth) ──────────────────────────────────────

def test_feedback(client):
    r = client.post("/v1/feedback", json={"action": "thumbs_up"})
    assert r.status_code == 201
    assert "id" in r.json()


# ── Metrics (no auth) ───────────────────────────────────────

def test_metrics_summary(client):
    r = client.get("/v1/metrics/summary")
    assert r.status_code == 200


# ── Auth-required routes return 401 without key ─────────────

def test_objects_requires_auth(client):
    r = client.get("/v1/objects")
    assert r.status_code == 401


def test_edges_requires_auth(client):
    r = client.get("/v1/edges")
    assert r.status_code == 401


def test_create_object_requires_auth(client):
    r = client.post("/v1/objects", json={
        "workspace_id": str(uuid.uuid4()),
        "slug": "test",
        "type": "concept_note",
        "canonical_title": "Test",
    })
    assert r.status_code == 401


def test_evidence_requires_auth(client):
    r = client.post("/v1/evidence/sources", json={
        "source_kind": "BOOK",
        "title": "Test Source",
    })
    assert r.status_code == 401


def test_reviews_requires_auth(client):
    r = client.post("/v1/reviews", json={
        "version_id": str(uuid.uuid4()),
        "verdict": "approved",
    })
    assert r.status_code == 401


def test_retrieval_requires_auth(client):
    r = client.post("/v1/retrieve/evidence_pack", json={
        "query": "test",
        "intent": "how_to",
    })
    assert r.status_code == 401


def test_ingest_requires_auth(client):
    r = client.post("/v1/ingest/jobs", json={
        "source_id": "src.test.book.2024",
        "source_title": "Test Book",
    })
    assert r.status_code == 401


def test_review_queue_requires_auth(client):
    r = client.get("/v1/reviews/queue")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_smoke_api.py -v`
Expected: 16 tests PASS (these run without a live DB for auth-rejection tests; public endpoints may need DB)

- [ ] **Step 3: Commit**

```bash
git add tests/test_smoke_api.py
git commit -m "test: add API smoke tests for all route modules"
```

---

### Task 6: Update CI Workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Update the integration job to run all integration test files**

Change line 66 from:
```yaml
      - run: pytest tests/test_integration.py -v
```
to:
```yaml
      - run: pytest tests/test_integration.py tests/test_integration_embedding.py tests/test_integration_publication.py tests/test_integration_search.py tests/test_integration_retrieval.py -v
```

And update line 39 to ignore all integration tests:
```yaml
      - run: pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_integration_embedding.py --ignore=tests/test_integration_publication.py --ignore=tests/test_integration_search.py --ignore=tests/test_integration_retrieval.py -v
```

- [ ] **Step 2: Verify YAML validity**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run new integration tests in CI integration job"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run the full unit test suite**

Run: `pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_integration_embedding.py --ignore=tests/test_integration_publication.py --ignore=tests/test_integration_search.py --ignore=tests/test_integration_retrieval.py -v`
Expected: All existing + new smoke tests PASS

- [ ] **Step 2: Run all integration tests (requires live Postgres)**

Run: `pytest tests/test_integration.py tests/test_integration_embedding.py tests/test_integration_publication.py tests/test_integration_search.py tests/test_integration_retrieval.py -v`
Expected: All integration tests PASS

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "test: fix any integration test issues"
```
