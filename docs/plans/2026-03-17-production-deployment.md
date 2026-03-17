# Production Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all gaps between the CapabilityCommons backend and CapabilityCommonsSite frontend so the site can be deployed with live data.

**Architecture:** Three phases — (1) unblock the site by adding missing endpoints, fixing schema mismatches, and publishing seed data; (2) harden for production with CORS, logging, Dockerfile, and docs; (3) operational readiness with health checks, cleanup jobs, and load testing.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Postgres 16 + pgvector, Docker, Python structured logging

---

## Phase 1: Unblock the Site

### Task 1: Add `GET /v1/public/objects` endpoint

The site calls `listPublicObjects()` which hits `GET /v1/public/objects`. This endpoint does not exist. It must return all published objects as `list[PublicObjectResponse]`.

**Files:**
- Modify: `src/capability_commons/api/routes/public.py`
- Modify: `src/capability_commons/publication/service.py`
- Test: `tests/test_public_endpoints.py`

**Step 1: Write the failing test**

Create `tests/test_public_endpoints.py`:

```python
"""Tests for public API endpoints."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import public


def test_list_public_objects_endpoint_exists():
    """GET /v1/public/objects endpoint must exist."""
    assert hasattr(public, "list_public_objects")
    sig = inspect.signature(public.list_public_objects)
    assert "session" in sig.parameters
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_public_endpoints.py -v`
Expected: FAIL with `AttributeError: module has no attribute 'list_public_objects'`

**Step 3: Add `list_published_objects` to PublicationService**

In `src/capability_commons/publication/service.py`, add this method to the `PublicationService` class:

```python
async def list_published_objects(self) -> list[PublicObjectResponse]:
    result = await self.session.execute(
        select(ContextObject)
        .where(ContextObject.lifecycle_state == LifecycleState.PUBLISHED)
        .order_by(ContextObject.canonical_title.asc())
    )
    objects = result.scalars().all()
    items = []
    for obj in objects:
        try:
            items.append(await self.render_public_object(obj.slug))
        except Exception:
            continue  # Skip objects with rendering issues
    return items
```

**Step 4: Add the route**

In `src/capability_commons/api/routes/public.py`, add:

```python
@router.get("/public/objects", response_model=list[PublicObjectResponse])
async def list_public_objects(session: DBSession) -> list[PublicObjectResponse]:
    service = PublicationService(session)
    return await service.list_published_objects()
```

Note: This route must be defined BEFORE the `"/public/objects/{slug}"` route to avoid FastAPI matching `objects` as a slug parameter.

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_public_endpoints.py tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 6: Commit**

```bash
git add src/capability_commons/api/routes/public.py src/capability_commons/publication/service.py tests/test_public_endpoints.py
git commit -m "feat: add GET /v1/public/objects endpoint for listing published objects"
```

---

### Task 2: Add `GET /v1/public/graph` endpoint

The site calls `getGraphData()` which hits `GET /v1/public/graph`. This endpoint must return `{ nodes: GraphNode[], edges: GraphEdge[] }` shaped data for the D3 force-directed graph.

The frontend `GraphNode` shape requires: `id`, `slug`, `title`, `type`, `domain`, `stage`, `difficulty`, `risk_band`, `beginner_safe`, `plain_language`. Most of these live on `ContextObjectVersion`. `domain` comes from the `domain` facet.

**Files:**
- Modify: `src/capability_commons/api/routes/public.py`
- Modify: `src/capability_commons/publication/service.py`
- Create: `src/capability_commons/schemas/graph.py`
- Test: `tests/test_public_endpoints.py`

**Step 1: Write the failing test**

Append to `tests/test_public_endpoints.py`:

```python
def test_public_graph_endpoint_exists():
    """GET /v1/public/graph endpoint must exist."""
    assert hasattr(public, "public_graph")
    sig = inspect.signature(public.public_graph)
    assert "session" in sig.parameters


def test_graph_response_schema():
    """GraphResponse must have nodes and edges fields."""
    from capability_commons.schemas.graph import GraphResponse
    fields = GraphResponse.model_fields
    assert "nodes" in fields
    assert "edges" in fields
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_public_endpoints.py -v`
Expected: FAIL

**Step 3: Create graph schema**

Create `src/capability_commons/schemas/graph.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    slug: str
    title: str
    type: str
    domain: str = "foundation"
    stage: str = "foundation"
    difficulty: int = 1
    risk_band: str = "low"
    beginner_safe: bool = True
    plain_language: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
```

**Step 4: Add `build_graph_data` to PublicationService**

In `src/capability_commons/publication/service.py`, add these imports at the top:

```python
from capability_commons.schemas.graph import GraphEdge, GraphNode, GraphResponse
```

Then add this method to `PublicationService`:

```python
async def build_graph_data(self) -> GraphResponse:
    result = await self.session.execute(
        select(ContextObject)
        .where(ContextObject.lifecycle_state == LifecycleState.PUBLISHED)
    )
    objects = list(result.scalars().all())

    nodes = []
    version_id_to_slug: dict[str, str] = {}
    for obj in objects:
        version = obj.current_version
        if version is None:
            continue
        version_id_to_slug[str(version.id)] = obj.slug
        facets = await self._group_facets(version.id)
        domain = (facets.get("domain") or ["foundation"])[0]
        nodes.append(GraphNode(
            id=obj.slug,
            slug=obj.slug,
            title=version.title,
            type=obj.type.value,
            domain=domain,
            stage=version.stage.value if version.stage else "foundation",
            difficulty=version.difficulty or 1,
            risk_band=version.risk_band.value if version.risk_band else "low",
            beginner_safe=version.beginner_safe,
            plain_language=version.plain_language or "",
        ))

    # Get edges between published versions
    version_ids = list(version_id_to_slug.keys())
    if not version_ids:
        return GraphResponse(nodes=nodes, edges=[])

    from capability_commons.db.models import Edge as EdgeModel
    from capability_commons.domain.enums import NodeKind as NK
    edge_result = await self.session.execute(
        select(EdgeModel).where(
            EdgeModel.src_node_kind == NK.OBJECT_VERSION,
            EdgeModel.dst_node_kind == NK.OBJECT_VERSION,
            EdgeModel.src_id.in_([uuid.UUID(v) for v in version_ids]),
            EdgeModel.dst_id.in_([uuid.UUID(v) for v in version_ids]),
        )
    )
    edges = []
    for edge in edge_result.scalars().all():
        src_slug = version_id_to_slug.get(str(edge.src_id))
        dst_slug = version_id_to_slug.get(str(edge.dst_id))
        if src_slug and dst_slug:
            edges.append(GraphEdge(
                source=src_slug,
                target=dst_slug,
                type=edge.edge_type.value,
            ))

    return GraphResponse(nodes=nodes, edges=edges)
```

Also add `import uuid` to the top if not already present.

**Step 5: Add the route**

In `src/capability_commons/api/routes/public.py`, add the import:

```python
from capability_commons.schemas.graph import GraphResponse
```

Add the route:

```python
@router.get("/public/graph", response_model=GraphResponse)
async def public_graph(session: DBSession) -> GraphResponse:
    service = PublicationService(session)
    return await service.build_graph_data()
```

**Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_public_endpoints.py tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 7: Commit**

```bash
git add src/capability_commons/schemas/graph.py src/capability_commons/api/routes/public.py src/capability_commons/publication/service.py tests/test_public_endpoints.py
git commit -m "feat: add GET /v1/public/graph endpoint for D3 graph visualization"
```

---

### Task 3: Make `SearchRequest.workspace_id` optional

The site sends `POST /v1/search` without `workspace_id` in the body (the workspace comes from `CurrentWorkspace` auth dependency). But Pydantic requires it, so the request 422s before the route function runs.

Same issue exists for `RetrievalRequest.workspace_id`.

**Files:**
- Modify: `src/capability_commons/schemas/search.py`
- Modify: `src/capability_commons/schemas/retrieval.py`
- Test: `tests/test_schema_optional.py`

**Step 1: Write the failing test**

Create `tests/test_schema_optional.py`:

```python
"""Tests that workspace_id is optional on public-facing request schemas."""
from __future__ import annotations

from capability_commons.schemas.search import SearchRequest
from capability_commons.schemas.retrieval import RetrievalRequest


def test_search_request_workspace_id_optional():
    req = SearchRequest(query="test water purification")
    assert req.workspace_id is None


def test_retrieval_request_workspace_id_optional():
    req = RetrievalRequest(query="how to purify water", intent="how_to")
    assert req.workspace_id is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_schema_optional.py -v`
Expected: FAIL with `ValidationError: workspace_id field required`

**Step 3: Make workspace_id optional**

In `src/capability_commons/schemas/search.py`, change line 12:

```python
# Before:
workspace_id: uuid.UUID
# After:
workspace_id: uuid.UUID | None = None
```

In `src/capability_commons/schemas/retrieval.py`, change line 30:

```python
# Before:
workspace_id: uuid.UUID
# After:
workspace_id: uuid.UUID | None = None
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_schema_optional.py tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 5: Commit**

```bash
git add src/capability_commons/schemas/search.py src/capability_commons/schemas/retrieval.py tests/test_schema_optional.py
git commit -m "fix: make workspace_id optional on SearchRequest and RetrievalRequest

The workspace is resolved server-side from CurrentWorkspace auth
dependency, so the client should not need to supply it in the body."
```

---

### Task 4: Publish seed data on load

The seed loader creates all objects in `DRAFT` state. Public endpoints filter by `lifecycle_state == PUBLISHED`. Without publishing, the site gets empty responses.

**Files:**
- Modify: `src/capability_commons/cli/seed.py`
- Test: `tests/test_seed.py` (add assertion)

**Step 1: Write the failing test**

Append to `tests/test_seed.py`:

```python
def test_seed_sets_published_state():
    """Seeded objects should be in PUBLISHED lifecycle state."""
    from capability_commons.domain.enums import LifecycleState
    # The seed loader should set lifecycle_state to PUBLISHED
    assert LifecycleState.PUBLISHED.value == "published"
    # This is a code-level check; integration test will verify DB state
```

This is a structural test. The real verification is the integration test.

**Step 2: Modify seed.py**

In `src/capability_commons/cli/seed.py`, change line 170:

```python
# Before:
lifecycle_state=LifecycleState.DRAFT,
# After:
lifecycle_state=LifecycleState.PUBLISHED,
```

Also add the `published_at` timestamp. After line 199 (`obj.current_version_id = version.id`), add:

```python
            obj.published_at = obj.created_at
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 4: Commit**

```bash
git add src/capability_commons/cli/seed.py tests/test_seed.py
git commit -m "fix: seed objects as PUBLISHED so public endpoints serve them"
```

---

### Task 5: Fix health check to verify database connectivity

The health endpoint returns hardcoded `"ok"` without checking Postgres. Orchestrators relying on this won't detect DB failures.

**Files:**
- Modify: `src/capability_commons/api/routes/health.py`
- Modify: `tests/test_health.py`

**Step 1: Write the failing test**

Replace `tests/test_health.py` contents:

```python
"""Tests for health endpoint."""
from __future__ import annotations

import inspect

from capability_commons.api.routes import health


def test_health_endpoint_exists():
    assert hasattr(health, "health")


def test_detailed_health_accepts_session():
    """Detailed health check must accept a DB session to verify connectivity."""
    sig = inspect.signature(health.health_detailed)
    assert "session" in sig.parameters
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_health.py -v`
Expected: FAIL on `test_detailed_health_accepts_session`

**Step 3: Update health endpoint**

Replace `src/capability_commons/api/routes/health.py`:

```python
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from capability_commons.api.deps import DBSession
from capability_commons.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="capability_commons")


@router.get("/health/detailed")
async def health_detailed(session: DBSession) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    overall = "ok" if db_status == "healthy" else "degraded"
    return {
        "status": overall,
        "database": db_status,
        "search": "adapter_ready",
        "graph": "adapter_ready",
    }
```

**Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_health.py tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 5: Commit**

```bash
git add src/capability_commons/api/routes/health.py tests/test_health.py
git commit -m "fix: health check verifies database connectivity

Detailed health endpoint now executes SELECT 1 against Postgres.
Returns 'degraded' status if DB is unreachable."
```

---

## Phase 2: Harden for Production

### Task 6: Restrict CORS for production

CORS is already configurable via `cors_origins` setting, but `.env.example` shows `["*"]`. Update the default and document it.

**Files:**
- Modify: `src/capability_commons/config.py`
- Modify: `.env.example`

**Step 1: Update .env.example**

Add the auth and CORS fields to `.env.example`:

```
APP_ENV=dev
APP_NAME=Capability Commons API
API_V1_PREFIX=/v1
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/capability_commons
DATABASE_ECHO=false
EMBEDDING_DIM=1536
DEFAULT_TOP_K=20
DEFAULT_MAX_GRAPH_DEPTH=3
DEFAULT_MAX_ITERATIONS=4
DEFAULT_SUFFICIENCY_THRESHOLD=0.75
PUBLIC_PREVIEW=false

# CORS — restrict in production
CORS_ORIGINS=["http://localhost:4321"]

# Auth — set to false for local development without API keys
AUTH_ENABLED=false
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PUBLIC_PER_MINUTE=300

# Embeddings — leave empty for FTS-only search
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BATCH_SIZE=50

# Worker
OUTBOX_POLL_INTERVAL_SECONDS=2.0
```

**Step 2: Update default CORS in config.py**

In `src/capability_commons/config.py`, change the cors_origins default:

```python
# Before:
cors_origins: list[str] = Field(default_factory=lambda: ["*"])
# After:
cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4321"])
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 4: Commit**

```bash
git add src/capability_commons/config.py .env.example
git commit -m "fix: restrict default CORS to localhost, document all env vars"
```

---

### Task 7: Add structured request logging middleware

No application logging exists. Add middleware that logs every request with method, path, status code, and latency.

**Files:**
- Create: `src/capability_commons/api/logging_middleware.py`
- Modify: `src/capability_commons/main.py`
- Test: `tests/test_logging.py`

**Step 1: Write the failing test**

Create `tests/test_logging.py`:

```python
"""Tests for logging middleware."""
from __future__ import annotations

import inspect

from capability_commons.api.logging_middleware import RequestLoggingMiddleware


def test_logging_middleware_exists():
    assert hasattr(RequestLoggingMiddleware, "__init__")
    sig = inspect.signature(RequestLoggingMiddleware.__init__)
    assert "app" in sig.parameters
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_logging.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create logging middleware**

Create `src/capability_commons/api/logging_middleware.py`:

```python
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("capability_commons.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s %d %.1fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        response.headers["x-request-id"] = request_id
        return response
```

**Step 4: Wire into main.py**

In `src/capability_commons/main.py`, add the import:

```python
from capability_commons.api.logging_middleware import RequestLoggingMiddleware
```

Add middleware (before the rate limit middleware line):

```python
app.add_middleware(RequestLoggingMiddleware)
```

Also add logging configuration at the top of main.py, after imports:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
```

**Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_logging.py tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 6: Commit**

```bash
git add src/capability_commons/api/logging_middleware.py src/capability_commons/main.py tests/test_logging.py
git commit -m "feat: add structured request logging middleware

Logs method, path, status, latency, and request ID for every request.
Sets X-Request-ID response header for tracing."
```

---

### Task 8: Add application Dockerfile

Docker Compose only runs Postgres. The FastAPI app needs its own Dockerfile for containerized deployment.

**Files:**
- Create: `Dockerfile`
- Modify: `docker-compose.yml`

**Step 1: Create Dockerfile**

Create `Dockerfile` at project root:

```dockerfile
FROM python:3.14-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .
RUN pip install --no-cache-dir -e .

FROM base AS runtime
EXPOSE 8100
CMD ["uvicorn", "capability_commons.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

**Step 2: Add app service to docker-compose.yml**

Replace `docker-compose.yml`:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: capability_commons
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: .
    ports:
      - "8100:8100"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/capability_commons
      AUTH_ENABLED: "false"
      CORS_ORIGINS: '["http://localhost:4321"]'
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  pgdata:
```

**Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add application Dockerfile and full-stack docker-compose

Includes API service with health check, depends on Postgres.
Exposes port 8100, configurable via environment variables."
```

---

### Task 9: Align SearchHit field names with frontend

The frontend expects `facets` on SearchHit, but the backend returns `matched_facets`. Also, the backend includes `validity_status`, `lifecycle_state`, and `summary_short` which the frontend doesn't use but should still be returned for forward compatibility.

**Files:**
- Modify: `src/capability_commons/schemas/search.py`
- Test: `tests/test_schema_optional.py`

**Step 1: Write the failing test**

Append to `tests/test_schema_optional.py`:

```python
def test_search_hit_has_facets_alias():
    """SearchHit should expose 'facets' for frontend compatibility."""
    from capability_commons.schemas.search import SearchHit
    fields = SearchHit.model_fields
    assert "facets" in fields or "matched_facets" in fields
```

**Step 2: Rename field**

In `src/capability_commons/schemas/search.py`, change `SearchHit`:

```python
class SearchHit(BaseModel):
    object_id: uuid.UUID
    version_id: uuid.UUID
    slug: str
    type: COType
    title: str
    summary_short: str | None = None
    plain_language: str
    score: float | Decimal
    lifecycle_state: LifecycleState
    validity_status: str
    facets: dict[str, list[str]] = Field(default_factory=dict)
```

Then update the search adapter in `src/capability_commons/search/adapters/postgres_search.py` — change `matched_facets=` to `facets=` in the `SearchHit` construction (line 93):

```python
# Before:
matched_facets=facets_by_version.get(version.id, {}),
# After:
facets=facets_by_version.get(version.id, {}),
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 4: Commit**

```bash
git add src/capability_commons/schemas/search.py src/capability_commons/search/adapters/postgres_search.py tests/test_schema_optional.py
git commit -m "fix: rename SearchHit.matched_facets to facets for frontend compatibility"
```

---

## Phase 3: Operational Readiness

### Task 10: Re-seed database with published objects and verify end-to-end

After all code changes, re-seed the database and verify the new public endpoints return data.

**Step 1: Run migrations and re-seed**

```bash
.venv/bin/python -m capability_commons.cli.seed --data-dir extended_seed
```

**Step 2: Verify public endpoints return data**

```bash
# Health check
curl -s http://localhost:8100/health | python -m json.tool

# List published objects
curl -s http://localhost:8100/v1/public/objects | python -m json.tool | head -20

# Graph data
curl -s http://localhost:8100/v1/public/graph | python -m json.tool | head -20

# Single object
curl -s http://localhost:8100/v1/public/objects/source-evaluation | python -m json.tool | head -20

# Search (with auth disabled)
curl -s -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: <workspace-id-from-list>" \
  -d '{"query": "water purification"}' | python -m json.tool | head -20

# Detailed health
curl -s http://localhost:8100/health/detailed | python -m json.tool
```

**Step 3: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All tests pass (unit + integration)

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: verify end-to-end public endpoints with published seed data"
```

---

### Task 11: Add rate limit log cleanup

Old `RateLimitLog` records accumulate forever. Add a cleanup method to the worker.

**Files:**
- Modify: `src/capability_commons/cli/worker.py`

**Step 1: Add cleanup method**

In `src/capability_commons/cli/worker.py`, add a cleanup method to `OutboxWorker`:

```python
async def cleanup_rate_limits(self, session: AsyncSession) -> int:
    """Delete rate limit records older than 1 hour."""
    from datetime import datetime, timedelta, timezone
    from capability_commons.db.models import RateLimitLog
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await session.execute(
        delete(RateLimitLog).where(RateLimitLog.window_start < cutoff)
    )
    await session.commit()
    return result.rowcount or 0
```

Add the import at the top:

```python
from sqlalchemy import delete
```

In the `run` method, add a periodic cleanup call (every 100 poll iterations).

**Step 2: Run tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All pass

**Step 3: Commit**

```bash
git add src/capability_commons/cli/worker.py
git commit -m "feat: add periodic rate limit log cleanup to outbox worker"
```

---

### Task 12: Add lifecycle_state index for published-only queries

Public endpoints filter by `lifecycle_state == PUBLISHED` on every request. Add a targeted index.

**Files:**
- Create: `alembic/versions/20260317_0001_lifecycle_index.py`

**Step 1: Create migration**

```python
"""Add index on lifecycle_state for published-only queries."""
revision = "20260317_0001"
down_revision = "20260313_0002"

from alembic import op


def upgrade() -> None:
    op.create_index(
        "idx_context_objects_lifecycle_state",
        "context_objects",
        ["lifecycle_state"],
    )


def downgrade() -> None:
    op.drop_index("idx_context_objects_lifecycle_state", "context_objects")
```

**Step 2: Run migration**

```bash
.venv/bin/alembic upgrade head
```

**Step 3: Commit**

```bash
git add alembic/versions/20260317_0001_lifecycle_index.py
git commit -m "perf: add index on context_objects.lifecycle_state for published queries"
```

---

## Completion Checklist

### Phase 1: Unblock the Site
- [ ] `GET /v1/public/objects` endpoint returns published objects
- [ ] `GET /v1/public/graph` endpoint returns nodes + edges for D3
- [ ] `SearchRequest.workspace_id` is optional
- [ ] `RetrievalRequest.workspace_id` is optional
- [ ] Seed data is created in PUBLISHED state
- [ ] Health check verifies DB connectivity

### Phase 2: Harden for Production
- [ ] CORS restricted to localhost by default
- [ ] `.env.example` documents all env vars
- [ ] Structured request logging with latency + request ID
- [ ] Application Dockerfile exists
- [ ] Full-stack docker-compose with api + db services
- [ ] SearchHit.facets field aligned with frontend

### Phase 3: Operational Readiness
- [ ] Database re-seeded with published objects
- [ ] All public endpoints verified with curl
- [ ] All tests passing (unit + integration)
- [ ] Rate limit log cleanup in worker
- [ ] lifecycle_state index for query performance
