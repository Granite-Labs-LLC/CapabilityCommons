# Auth Wiring & Hybrid Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire `CurrentWorkspace` into all non-public routes so auth is enforced, and connect the embedding pipeline to the search endpoint so hybrid FTS+vector search works end-to-end.

**Architecture:** Routes currently accept `workspace_id` from the client request body with no validation. We replace that with server-side workspace resolution via API key (or X-Workspace-Id header in dev mode). For search, we add an optional embedding step that computes a query vector and delegates to `search_hybrid()` instead of `search()`.

**Tech Stack:** FastAPI dependency injection, SQLAlchemy 2.x async, OpenAI embeddings API

---

### Task 1: Wire Auth into Object Routes

**Files:**
- Modify: `src/capability_commons/api/routes/objects.py`

**Context:** Currently all object endpoints accept `workspace_id` from the client (either as a query param or inside `CreateObjectRequest`). We need to:
- Import `CurrentWorkspace` from deps
- Add `workspace: CurrentWorkspace` parameter to endpoints that need workspace scoping
- For `create_object`: override `request.workspace_id` with `workspace.id`
- For `list_objects`: replace the `workspace_id: uuid.UUID` query param with `workspace: CurrentWorkspace`
- For read-only endpoints (get_object, get_current_version, list_versions): these operate on object_id directly and don't need workspace — leave them as-is
- For mutation endpoints (create_version, update_version, publish_version, attach_facets, attach_entities): these also operate on object_id — leave them as-is (the object already belongs to a workspace)

**Step 1: Update objects.py**

Change the import line:
```python
from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
```

Update `list_objects` to use `CurrentWorkspace` instead of `workspace_id: uuid.UUID`:
```python
@router.get("/objects", response_model=PaginatedResponse[ObjectResponse])
async def list_objects(
    workspace: CurrentWorkspace,
    session: DBSession,
    cursor: str | None = None,
    limit: int = 20,
) -> PaginatedResponse[ObjectResponse]:
    params = PaginationParams(cursor=cursor, limit=min(limit, 100))
    service = RegistryService(session)
    objects, total = await service.list_objects(
        workspace.id, cursor_id=params.decode_cursor(), limit=params.limit,
    )
    items = objects[:params.limit]
    has_more = len(objects) > params.limit
    next_cursor = PaginatedResponse.encode_cursor(items[-1].id) if has_more and items else None
    return PaginatedResponse(
        items=[ObjectResponse.model_validate(obj, from_attributes=True) for obj in items],
        next_cursor=next_cursor,
        total_count=total,
    )
```

Update `create_object` to inject workspace:
```python
@router.post("/objects", response_model=ObjectResponse)
async def create_object(request: CreateObjectRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> ObjectResponse:
    request.workspace_id = workspace.id
    service = RegistryService(session)
    obj = await service.create_object(request, actor_id=actor_id)
    return ObjectResponse.model_validate(obj, from_attributes=True)
```

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All unit tests still pass

**Step 3: Commit**

```bash
git add src/capability_commons/api/routes/objects.py
git commit -m "feat: wire CurrentWorkspace auth into object routes"
```

---

### Task 2: Wire Auth into Entity, Edge, Evidence, and Review Routes

**Files:**
- Modify: `src/capability_commons/api/routes/entities.py`
- Modify: `src/capability_commons/api/routes/edges.py`
- Modify: `src/capability_commons/api/routes/evidence.py`
- Modify: `src/capability_commons/api/routes/reviews.py`

**Context:** Same pattern — import `CurrentWorkspace`, add it as a parameter to mutation endpoints, override the `workspace_id` from the request body.

**Step 1: Update entities.py**

```python
from capability_commons.api.deps import CurrentWorkspace, DBSession
```

Update `create_entity`:
```python
@router.post("/entities")
async def create_entity(request: CreateEntityRequest, session: DBSession, workspace: CurrentWorkspace) -> dict:
    service = EntityService(session)
    entity = await service.create_entity(
        workspace_id=workspace.id,
        entity_type=EntityType(request.entity_type),
        canonical_name=request.canonical_name,
        metadata=request.metadata,
    )
    return {
        "id": entity.id,
        "workspace_id": entity.workspace_id,
        "entity_type": entity.entity_type.value,
        "canonical_name": entity.canonical_name,
        "metadata": entity.metadata_json,
    }
```

`add_alias` doesn't take workspace_id — leave as-is.

**Step 2: Update edges.py**

```python
from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
```

Update `create_edge`:
```python
@router.post("/edges", response_model=EdgeResponse)
async def create_edge(request: CreateEdgeRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> EdgeResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = RegistryService(session)
    edge = await service.create_edge(**data, created_by=actor_id)
    return EdgeResponse.model_validate(edge, from_attributes=True)
```

`list_edges` doesn't take workspace_id — leave as-is (it filters by src_id/dst_id).

**Step 3: Update evidence.py**

```python
from capability_commons.api.deps import ActorID, CurrentWorkspace, DBSession
```

Update `create_source`:
```python
@router.post("/evidence/sources", response_model=EvidenceSourceResponse)
async def create_source(request: CreateEvidenceSourceRequest, session: DBSession, actor_id: ActorID, workspace: CurrentWorkspace) -> EvidenceSourceResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = EvidenceService(session)
    source = await service.create_source(created_by=actor_id, **data)
    return EvidenceSourceResponse.model_validate(source, from_attributes=True)
```

Other evidence endpoints don't take workspace_id — leave as-is.

**Step 4: Update reviews.py**

```python
from capability_commons.api.deps import CurrentWorkspace, DBSession
```

Update `submit_review` and `open_contradiction`:
```python
@router.post("/reviews", response_model=ReviewResponse)
async def submit_review(request: CreateReviewRequest, session: DBSession, workspace: CurrentWorkspace) -> ReviewResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = ReviewService(session)
    review = await service.submit_review(**data)
    return ReviewResponse.model_validate(review, from_attributes=True)


@router.post("/contradictions", response_model=ContradictionResponse)
async def open_contradiction(request: OpenContradictionRequest, session: DBSession, workspace: CurrentWorkspace) -> ContradictionResponse:
    data = request.model_dump()
    data["workspace_id"] = workspace.id
    service = ReviewService(session)
    contradiction = await service.open_contradiction(**data)
    return ContradictionResponse.model_validate(contradiction, from_attributes=True)
```

Other review endpoints (resolve, verify, dispute, deprecate) don't take workspace_id — leave as-is.

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All unit tests still pass

**Step 6: Commit**

```bash
git add src/capability_commons/api/routes/entities.py src/capability_commons/api/routes/edges.py src/capability_commons/api/routes/evidence.py src/capability_commons/api/routes/reviews.py
git commit -m "feat: wire CurrentWorkspace auth into entity, edge, evidence, and review routes"
```

---

### Task 3: Wire Auth into Search and Retrieval Routes

**Files:**
- Modify: `src/capability_commons/api/routes/search.py`
- Modify: `src/capability_commons/api/routes/retrieval.py`

**Step 1: Update search.py**

```python
from capability_commons.api.deps import CurrentWorkspace, DBSession
```

Update the search endpoint to use workspace from auth instead of request body:
```python
@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, session: DBSession, workspace: CurrentWorkspace) -> SearchResponse:
    adapter = PostgresSearchAdapter(session)
    hits = await adapter.search(
        workspace_id=workspace.id,
        query=request.query,
        filters=request.facet_filters,
        top_k=request.top_k,
        object_types=request.object_types,
        only_published=request.only_published,
    )
    return SearchResponse(query=request.query, top_k=request.top_k, hits=hits)
```

**Step 2: Update retrieval.py**

```python
from capability_commons.api.deps import CurrentWorkspace, DBSession
```

Update `retrieve_evidence_pack`:
```python
@router.post("/retrieve/evidence_pack")
async def retrieve_evidence_pack(
    request: RetrievalRequest,
    session: DBSession,
    workspace: CurrentWorkspace,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
):
    request.workspace_id = workspace.id
    service = RetrievalService(session)
    pack = await service.execute_plan(request)
    if format == "markdown":
        return PlainTextResponse(pack.rendered_markdown or "")
    return JSONResponse(content=pack.model_dump(mode="json"))
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All unit tests still pass

**Step 4: Commit**

```bash
git add src/capability_commons/api/routes/search.py src/capability_commons/api/routes/retrieval.py
git commit -m "feat: wire CurrentWorkspace auth into search and retrieval routes"
```

---

### Task 4: Write Auth Wiring Tests

**Files:**
- Create: `tests/test_auth_wiring.py`

**Step 1: Write tests that verify routes require auth**

```python
"""Tests that verify auth is wired into route handler signatures."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import edges, entities, evidence, objects, retrieval, reviews, search


def _has_workspace_param(func) -> bool:
    """Check if a route handler has a 'workspace' parameter."""
    sig = inspect.signature(func)
    return "workspace" in sig.parameters


def test_object_list_requires_workspace():
    assert _has_workspace_param(objects.list_objects)


def test_object_create_requires_workspace():
    assert _has_workspace_param(objects.create_object)


def test_entity_create_requires_workspace():
    assert _has_workspace_param(entities.create_entity)


def test_edge_create_requires_workspace():
    assert _has_workspace_param(edges.create_edge)


def test_evidence_create_source_requires_workspace():
    assert _has_workspace_param(evidence.create_source)


def test_review_submit_requires_workspace():
    assert _has_workspace_param(reviews.submit_review)


def test_contradiction_open_requires_workspace():
    assert _has_workspace_param(reviews.open_contradiction)


def test_search_requires_workspace():
    assert _has_workspace_param(search.search)


def test_retrieval_requires_workspace():
    assert _has_workspace_param(retrieval.retrieve_evidence_pack)


def test_public_routes_do_not_require_workspace():
    """Public routes should NOT require auth."""
    from capability_commons.api.routes import public
    assert not _has_workspace_param(public.public_object)
    assert not _has_workspace_param(public.public_module)
    assert not _has_workspace_param(public.public_path)
    assert not _has_workspace_param(public.public_bundle)
```

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_auth_wiring.py -v`
Expected: All 10 tests PASS

**Step 3: Commit**

```bash
git add tests/test_auth_wiring.py
git commit -m "test: verify auth workspace dependency is wired into all mutation routes"
```

---

### Task 5: Connect Hybrid Search to the Search Endpoint

**Files:**
- Modify: `src/capability_commons/api/routes/search.py`
- Modify: `src/capability_commons/services/embedding.py`

**Context:** The `search_hybrid()` method already exists on `PostgresSearchAdapter`. The `EmbeddingService` and `OpenAIEmbeddingProvider` already exist. We need to:
1. Add a method to `EmbeddingService` (or provider) to embed a single query string
2. Update the search endpoint to compute a query embedding when available, then call `search_hybrid`

**Step 1: Add `embed_query` to EmbeddingService**

Add this method to `EmbeddingService` in `src/capability_commons/services/embedding.py`:

```python
    async def embed_query(self, text: str) -> list[float] | None:
        """Embed a single query string. Returns None if no provider configured."""
        if self.provider is None:
            return None
        results = await self.provider.embed([text])
        return results[0]
```

**Step 2: Update search endpoint to use hybrid search**

Replace `src/capability_commons/api/routes/search.py`:

```python
from __future__ import annotations

import logging

from fastapi import APIRouter

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.schemas.search import SearchRequest, SearchResponse
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
from capability_commons.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, session: DBSession, workspace: CurrentWorkspace) -> SearchResponse:
    adapter = PostgresSearchAdapter(session)
    embedding_svc = EmbeddingService(session)

    query_embedding = await embedding_svc.embed_query(request.query)

    hits = await adapter.search_hybrid(
        workspace_id=workspace.id,
        query=request.query,
        query_embedding=query_embedding,
        filters=request.facet_filters,
        top_k=request.top_k,
        object_types=request.object_types,
        only_published=request.only_published,
    )
    return SearchResponse(query=request.query, top_k=request.top_k, hits=hits)
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/capability_commons/api/routes/search.py src/capability_commons/services/embedding.py
git commit -m "feat: connect hybrid FTS+vector search to search endpoint

- Add embed_query() to EmbeddingService for single-string embedding
- Search endpoint now computes query embedding when OPENAI_API_KEY set
- Falls back to pure FTS when no embedding provider configured"
```

---

### Task 6: Write Hybrid Search Test

**Files:**
- Modify: `tests/test_embedding.py`

**Step 1: Add embed_query test**

Append to `tests/test_embedding.py`:

```python
@pytest.mark.asyncio
async def test_embed_query_with_provider():
    session = AsyncMock()
    provider = FakeProvider()
    service = EmbeddingService(session, provider=provider)
    result = await service.embed_query("test query")
    assert result is not None
    assert len(result) == 10


@pytest.mark.asyncio
async def test_embed_query_no_provider():
    session = AsyncMock()
    service = EmbeddingService(session, provider=None)
    service.provider = None
    result = await service.embed_query("test query")
    assert result is None
```

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/test_embedding.py -v`
Expected: All 4 tests PASS

**Step 3: Commit**

```bash
git add tests/test_embedding.py
git commit -m "test: add embed_query unit tests for provider and no-provider paths"
```

---

### Task 7: Fix Integration Test Fixtures

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_integration.py`

**Context:** The current conftest.py wraps the session in `session.begin()` which conflicts with service-layer `commit()` calls. Fix by removing the transaction wrapper and using cleanup instead. Also, integration tests need to pass `workspace` through `CurrentWorkspace` now.

NOTE: Integration tests hit a real database. If the DB isn't running, they will fail — that's expected. The goal is to make them structurally correct.

**Step 1: Fix conftest.py**

Replace `tests/conftest.py`:

```python
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.domain.enums import WorkspaceVisibility


@pytest_asyncio.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        # Clean up test data by deleting the test workspace (cascades)
        await session.execute(
            text("DELETE FROM workspaces WHERE slug LIKE 'test-%'")
        )
        await session.commit()

    await engine.dispose()


@pytest_asyncio.fixture
async def workspace(db_session: AsyncSession):
    ws = Workspace(
        slug=f"test-{uuid.uuid4().hex[:8]}",
        name="Test Workspace",
        visibility=WorkspaceVisibility.PUBLIC,
    )
    db_session.add(ws)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(ws)
    return ws
```

**Step 2: Fix test_integration.py**

The integration tests call service methods directly — they don't go through HTTP routes, so they don't need `CurrentWorkspace`. The fix is just the conftest session management. Keep `test_integration.py` as-is.

**Step 3: Run integration tests (if DB available)**

Run: `.venv/bin/pytest tests/test_integration.py -v 2>&1 | tail -20`
Expected: PASS if DB is running, connection error if not

**Step 4: Run unit tests to verify conftest doesn't break them**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All unit tests pass

**Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "fix: integration test fixtures use cleanup instead of rollback

- Remove session.begin() wrapper that conflicted with service commit()
- Clean up test data by deleting test workspaces after each test
- Flush and commit workspace creation so service layer sees it"
```

---

## Completion Checklist

- [ ] Object routes use CurrentWorkspace (list, create)
- [ ] Entity, edge, evidence, review routes use CurrentWorkspace
- [ ] Search and retrieval routes use CurrentWorkspace
- [ ] Public routes do NOT require workspace auth
- [ ] Auth wiring verified by tests
- [ ] Search endpoint calls search_hybrid with query embedding
- [ ] embed_query method on EmbeddingService
- [ ] Hybrid search tested
- [ ] Integration test fixtures fixed
- [ ] All unit tests passing
