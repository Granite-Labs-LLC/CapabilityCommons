# Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Capability Commons for production deployment by adding CI/CD, observability, connection pooling, auth improvements, and missing test coverage.

**Architecture:** Add production infrastructure in layers: (1) CI pipeline for quality gates, (2) observability stack (structured logging, Sentry, Prometheus), (3) database hardening (pooling, migration checks), (4) auth improvements (key rotation), (5) developer experience (Swagger, mypy), (6) test gap coverage. Each task is independent and can be completed in any order.

**Tech Stack:** GitHub Actions, structlog, sentry-sdk, prometheus-fastapi-instrumentator, SQLAlchemy pool config, Alembic, mypy, pytest

---

## File Structure

### New files
- `.github/workflows/ci.yml` — CI pipeline (lint, test, type-check, Docker build, integration test)
- `tests/test_evidence_routes.py` — Evidence route tests
- `tests/test_review_routes.py` — Review route tests

### Modified files
- `pyproject.toml` — Add structlog, sentry-sdk, prometheus-fastapi-instrumentator to deps; add `[tool.mypy]` config; add ruff config
- `src/capability_commons/config.py` — Add pool, Sentry, and key expiry settings
- `src/capability_commons/main.py` — Wire structlog, Sentry, Prometheus, Swagger, migration check
- `src/capability_commons/api/logging_middleware.py` — Switch to structlog
- `src/capability_commons/api/routes/health.py` — Deepen health checks
- `src/capability_commons/db/session.py` — Add pool configuration
- `src/capability_commons/db/models.py` — Add `expire_at` to ApiKey
- `src/capability_commons/api/auth.py` — Check `expire_at` in key resolution
- `src/capability_commons/cli/keys.py` — Add `rotate` command
- `alembic/versions/20260325_0001_api_key_expire_at.py` — Migration for `expire_at` column
- `tests/test_health.py` — Update health tests
- `tests/test_auth.py` — Add key expiry tests

---

## Chunk 1: CI/CD and Developer Tooling

### Task 1: GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` (add ruff to dev deps)

- [ ] **Step 1: Create `.github/workflows/` directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Add ruff to dev dependencies in pyproject.toml**

In `pyproject.toml`, add `ruff` to the `[project.optional-dependencies] dev` list:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.4,<9.0",
  "pytest-asyncio>=0.26,<1.0",
  "httpx>=0.28,<1.0",
  "asgi-lifespan>=2.1,<3.0",
  "ruff>=0.11,<1.0",
  "mypy>=1.15,<2.0",
]
```

- [ ] **Step 3: Write the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - run: pip install -e '.[dev]'
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - run: pip install -e '.[dev]'
      - run: mypy src/capability_commons/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - run: pip install -e '.[dev]'
      - run: pytest tests/ --ignore=tests/test_integration.py -v

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: capability_commons
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - run: pip install -e '.[dev]'
      - run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/capability_commons
      - run: pytest tests/test_integration.py -v
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/capability_commons

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t capability-commons:ci .
```

- [ ] **Step 4: Verify the workflow YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: No error (valid YAML).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml
git commit -m "ci: add GitHub Actions workflow for lint, test, typecheck, and Docker build"
```

---

### Task 2: mypy Configuration

**Files:**
- Modify: `pyproject.toml` (add `[tool.mypy]` section)

- [ ] **Step 1: Add mypy configuration to pyproject.toml**

Append after the existing `[tool.pytest.ini_options]` section:

```toml
[tool.mypy]
python_version = "3.14"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
ignore_missing_imports = true
exclude = ["alembic/", "tests/"]

[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "W"]
ignore = ["E501"]
```

Note: `disallow_untyped_defs = false` and `ignore_missing_imports = true` keep the initial adoption incremental — the codebase already uses type hints but doesn't have stubs for all dependencies. This can be tightened later.

- [ ] **Step 2: Run mypy to verify it works**

```bash
mypy src/capability_commons/ 2>&1 | tail -5
```
Expected: mypy runs and reports results (may have warnings — that's fine for now).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mypy and ruff configuration"
```

---

## Chunk 2: Observability

### Task 3: Structured Logging with structlog

**Files:**
- Modify: `pyproject.toml` (add structlog dependency)
- Modify: `src/capability_commons/main.py` (configure structlog)
- Modify: `src/capability_commons/api/logging_middleware.py` (switch to structlog)
- Modify: `tests/test_logging.py` (update tests)

- [ ] **Step 1: Add structlog to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```
  "structlog>=24.0,<25.0",
```

- [ ] **Step 2: Read the existing logging test**

```bash
cat tests/test_logging.py
```

Understand what the current test expects so we don't break it.

- [ ] **Step 3: Update the logging middleware to use structlog**

Replace the entire contents of `src/capability_commons/api/logging_middleware.py`:

```python
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("capability_commons.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed_ms, 1),
            request_id=request_id,
        )
        response.headers["x-request-id"] = request_id
        return response
```

- [ ] **Step 4: Configure structlog in main.py**

Replace the `logging.basicConfig(...)` block (lines 15-18) in `src/capability_commons/main.py` with:

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "dev"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
```

This gives dev-friendly colored console output in development and JSON in production. The `import logging` at the top of main.py should remain (structlog uses it for filtering).

- [ ] **Step 5: Update logging tests if needed**

Read and fix `tests/test_logging.py` if it imports or patches the old logger format. The middleware class name (`RequestLoggingMiddleware`) stays the same, and the structlog logger still gets called with the same data — just in structured form.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_logging.py tests/test_health.py -v
```
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/capability_commons/main.py src/capability_commons/api/logging_middleware.py tests/test_logging.py
git commit -m "feat: switch to structlog for structured JSON logging in production"
```

---

### Task 4: Sentry Error Tracking

**Files:**
- Modify: `pyproject.toml` (add sentry-sdk dependency)
- Modify: `src/capability_commons/config.py` (add sentry_dsn setting)
- Modify: `src/capability_commons/main.py` (initialize Sentry)

- [ ] **Step 1: Add sentry-sdk to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```
  "sentry-sdk[fastapi]>=2.0,<3.0",
```

- [ ] **Step 2: Add sentry_dsn to config**

In `src/capability_commons/config.py`, add to the `Settings` class after the Worker section:

```python
    # Observability
    sentry_dsn: str = ""
```

- [ ] **Step 3: Initialize Sentry in main.py**

Add after the structlog configuration block and before the `app = FastAPI(...)` line:

```python
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment=settings.app_env,
    )
```

- [ ] **Step 4: Run tests to verify nothing breaks**

```bash
pytest tests/test_health.py -v
```
Expected: Pass (Sentry is not initialized when DSN is empty).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/capability_commons/config.py src/capability_commons/main.py
git commit -m "feat: add Sentry error tracking (opt-in via SENTRY_DSN env var)"
```

---

### Task 5: Prometheus Metrics

**Files:**
- Modify: `pyproject.toml` (add prometheus-fastapi-instrumentator)
- Modify: `src/capability_commons/main.py` (wire instrumentator)
- Modify: `src/capability_commons/config.py` (add metrics_enabled setting)

- [ ] **Step 1: Add prometheus dependency**

In `pyproject.toml`, add to the `dependencies` list:

```
  "prometheus-fastapi-instrumentator>=7.0,<8.0",
```

- [ ] **Step 2: Add metrics_enabled setting**

In `src/capability_commons/config.py`, add to the `Settings` class in the Observability section:

```python
    metrics_enabled: bool = True
```

- [ ] **Step 3: Wire Prometheus in main.py**

Add after the CORS middleware block and before `register_error_handlers(app)`:

```python
if settings.metrics_enabled:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

This auto-instruments all routes and exposes a `/metrics` endpoint for Prometheus scraping.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_health.py -v
```
Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/capability_commons/config.py src/capability_commons/main.py
git commit -m "feat: add Prometheus metrics endpoint via prometheus-fastapi-instrumentator"
```

---

## Chunk 3: Database Hardening

### Task 6: Connection Pooling Configuration

**Files:**
- Modify: `src/capability_commons/config.py` (add pool settings)
- Modify: `src/capability_commons/db/session.py` (pass pool settings to engine)

- [ ] **Step 1: Add pool settings to config**

In `src/capability_commons/config.py`, add to the `Settings` class after the `database_echo` field:

```python
    # Connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
```

- [ ] **Step 2: Update engine creation to use pool settings**

Replace `src/capability_commons/db/session.py` entirely:

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings

settings = get_settings()
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Run tests to verify nothing breaks**

```bash
pytest tests/ --ignore=tests/test_integration.py -v 2>&1 | tail -10
```
Expected: All 115 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/capability_commons/config.py src/capability_commons/db/session.py
git commit -m "feat: add configurable connection pooling for production database loads"
```

---

### Task 7: Migration Safety Check on Startup

**Files:**
- Modify: `src/capability_commons/main.py` (add startup event)

- [ ] **Step 1: Write the migration check test**

Add to `tests/test_health.py`:

```python
def test_check_migrations_function_exists():
    """Migration check function should be importable."""
    from capability_commons.main import check_pending_migrations
    import inspect
    assert callable(check_pending_migrations)
    assert inspect.iscoroutinefunction(check_pending_migrations) is False  # sync function
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_health.py::test_check_migrations_function_exists -v
```
Expected: FAIL with `ImportError: cannot import name 'check_pending_migrations'`.

- [ ] **Step 3: Add the migration check function and lifespan event**

In `src/capability_commons/main.py`, add the import and function before the `app = FastAPI(...)` line:

```python
from contextlib import asynccontextmanager

def check_pending_migrations() -> None:
    """Log a warning if there are pending Alembic migrations."""
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine, inspect as sa_inspect

        sync_url = settings.database_url.replace("+asyncpg", "")
        sync_engine = create_engine(sync_url)
        with sync_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_heads = set(context.get_current_heads())
            script = ScriptDirectory.from_config(Config("alembic.ini"))
            expected_heads = set(script.get_heads())
            if current_heads != expected_heads:
                import structlog
                log = structlog.get_logger()
                log.warning(
                    "pending_migrations",
                    current=list(current_heads),
                    expected=list(expected_heads),
                )
        sync_engine.dispose()
    except Exception:
        pass  # Don't block startup if alembic check fails (e.g., in test environments)


@asynccontextmanager
async def lifespan(app):
    check_pending_migrations()
    yield
```

Then change the FastAPI constructor to use the lifespan:

```python
app = FastAPI(title=settings.app_name, lifespan=lifespan)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_health.py -v
```
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/main.py tests/test_health.py
git commit -m "feat: add migration safety check on startup (warns if pending migrations)"
```

---

### Task 8: Deeper Health Checks

**Files:**
- Modify: `src/capability_commons/api/routes/health.py` (add migration + embedding checks)
- Modify: `tests/test_health.py` (update tests)

- [ ] **Step 1: Write the test**

Add to `tests/test_health.py`:

```python
def test_detailed_health_returns_extended_fields():
    """Detailed health response should include migration and embedding info."""
    import inspect
    from capability_commons.api.routes import health
    sig = inspect.signature(health.health_detailed)
    # The function should accept a session parameter
    assert "session" in sig.parameters
```

This is a structural test — the full integration test requires a live DB and lives in `test_integration.py`.

- [ ] **Step 2: Update the health check route**

Replace `src/capability_commons/api/routes/health.py`:

```python
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from capability_commons.api.deps import DBSession
from capability_commons.config import get_settings
from capability_commons.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="capability_commons")


@router.get("/health/detailed")
async def health_detailed(session: DBSession) -> dict:
    settings = get_settings()
    checks: dict[str, str] = {}

    # Database connectivity
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Migration version
    try:
        result = await session.execute(
            text("SELECT version_num FROM alembic_version ORDER BY version_num")
        )
        versions = [row[0] for row in result.fetchall()]
        checks["migration_heads"] = ",".join(versions) if versions else "none"
    except Exception:
        checks["migration_heads"] = "unknown"

    # Embedding service availability
    checks["embedding_configured"] = "yes" if settings.openai_api_key else "no"

    overall = "ok" if checks["database"] == "healthy" else "degraded"
    return {"status": overall, **checks}
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_health.py -v
```
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add src/capability_commons/api/routes/health.py tests/test_health.py
git commit -m "feat: deepen health check to report migration version and embedding availability"
```

---

## Chunk 4: Auth Improvements

### Task 9: API Key Rotation (expire_at column + migration + auth check + CLI)

**Files:**
- Create: `alembic/versions/20260325_0001_api_key_expire_at.py`
- Modify: `src/capability_commons/db/models.py` (add expire_at to ApiKey)
- Modify: `src/capability_commons/api/auth.py` (check expire_at)
- Modify: `src/capability_commons/cli/keys.py` (add rotate command, --ttl flag)
- Modify: `tests/test_auth.py` (add expiry tests)

- [ ] **Step 1: Write the test for expired key rejection**

Add to `tests/test_auth.py`:

```python
from datetime import datetime, timedelta, timezone
from capability_commons.db.models import ApiKey


def test_api_key_model_has_expire_at():
    """ApiKey model should have an expire_at column."""
    assert hasattr(ApiKey, "expire_at")


def test_expired_key_check():
    """The auth module should expose an is_expired helper."""
    from capability_commons.api.auth import is_key_expired
    now = datetime.now(timezone.utc)

    # Not expired (future)
    assert is_key_expired(now + timedelta(hours=1)) is False
    # Expired (past)
    assert is_key_expired(now - timedelta(hours=1)) is True
    # No expiry set
    assert is_key_expired(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py::test_api_key_model_has_expire_at tests/test_auth.py::test_expired_key_check -v
```
Expected: FAIL.

- [ ] **Step 3: Add expire_at to the ApiKey model**

In `src/capability_commons/db/models.py`, add to the `ApiKey` class (after `revoked_at`):

```python
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Add the is_key_expired helper and update resolve_api_key**

In `src/capability_commons/api/auth.py`, add:

```python
from datetime import datetime, timezone


def is_key_expired(expire_at: datetime | None) -> bool:
    """Check if a key has expired. Returns False if no expiry is set."""
    if expire_at is None:
        return False
    return datetime.now(timezone.utc) >= expire_at
```

Then update `resolve_api_key` to check expiry after finding the key:

```python
async def resolve_api_key(session: AsyncSession, raw_key: str) -> tuple[ApiKey, Workspace] | None:
    key_hash = hash_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if is_key_expired(api_key.expire_at):
        return None
    workspace = await session.get(Workspace, api_key.workspace_id)
    if workspace is None:
        return None
    return api_key, workspace
```

- [ ] **Step 5: Create the Alembic migration**

Create `alembic/versions/20260325_0001_api_key_expire_at.py`:

```python
"""Add expire_at to api_keys table.

Revision ID: 20260325_0001
Revises: 20260323_0001
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260325_0001"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "expire_at")
```

Note: `down_revision` should match the latest existing migration. Check `alembic/versions/` for the actual revision ID of `20260323_0001_evidence_external_id.py` and use that.

- [ ] **Step 6: Add rotate command to keys CLI**

In `src/capability_commons/cli/keys.py`, add a `rotate_key` function and wire it into the CLI:

```python
from datetime import timedelta


async def rotate_key(db_url: str, old_key_id: str, name: str | None = None, ttl_hours: int | None = None) -> None:
    """Revoke the old key and create a new one in the same workspace."""
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        old = await session.get(ApiKey, uuid.UUID(old_key_id))
        if old is None:
            print(f"ERROR: API key '{old_key_id}' not found")
            await engine.dispose()
            return

        # Revoke old key
        old.revoked_at = datetime.now(timezone.utc)

        # Create new key
        raw_key, key_hash = generate_key()
        expire_at = None
        if ttl_hours is not None:
            expire_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        new_key = ApiKey(
            workspace_id=old.workspace_id,
            key_hash=key_hash,
            name=name or old.name,
            expire_at=expire_at,
        )
        session.add(new_key)
        await session.commit()

    await engine.dispose()
    print(f"Old key '{old_key_id}' revoked.")
    print(f"New key created:")
    print(f"  Name: {new_key.name}")
    print(f"  Key:  {raw_key}")
    print(f"  ID:   {new_key.id}")
    if expire_at:
        print(f"  Expires: {expire_at.isoformat()}")
    print()
    print("Store this key securely — it cannot be retrieved again.")
```

Add to the argparse section in `main()`:

```python
    rotate_p = sub.add_parser("rotate")
    rotate_p.add_argument("--key-id", required=True, help="API key UUID to rotate")
    rotate_p.add_argument("--name", default=None, help="New key name (default: same as old)")
    rotate_p.add_argument("--ttl-hours", type=int, default=None, help="Hours until new key expires")
    rotate_p.add_argument("--db-url", default=None)
```

And in the dispatch section:

```python
    elif args.command == "rotate":
        asyncio.run(rotate_key(db_url, args.key_id, args.name, args.ttl_hours))
```

Also update `create_key` to accept an optional `ttl_hours` parameter and add `--ttl-hours` flag to the `create` subparser, passing `expire_at` when creating the key.

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_auth.py -v
```
Expected: All pass (including new expiry tests).

- [ ] **Step 8: Commit**

```bash
git add src/capability_commons/db/models.py src/capability_commons/api/auth.py \
  src/capability_commons/cli/keys.py alembic/versions/20260325_0001_api_key_expire_at.py \
  tests/test_auth.py
git commit -m "feat: add API key expiry (expire_at) with rotation CLI command"
```

---

## Chunk 5: Developer Experience

### Task 10: Enable Swagger UI

**Files:**
- Modify: `src/capability_commons/main.py` (enable docs_url)

- [ ] **Step 1: Write the test**

Add to `tests/test_health.py`:

```python
def test_swagger_ui_accessible():
    """Swagger UI should be accessible at /docs."""
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_health.py::test_swagger_ui_accessible -v
```
Expected: FAIL (currently returns 404 or redirect since docs aren't enabled).

- [ ] **Step 3: Enable Swagger in main.py**

Change the `FastAPI` constructor:

```python
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
```

Note: If you haven't done Task 7 yet (lifespan), omit the `lifespan=lifespan` parameter.

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_health.py -v
```
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/main.py tests/test_health.py
git commit -m "feat: enable Swagger UI at /docs and ReDoc at /redoc"
```

---

## Chunk 6: Test Coverage Gaps

### Task 11: Evidence Route Tests

**Files:**
- Create: `tests/test_evidence_routes.py`

These tests verify the evidence routes at the HTTP level using the test client pattern established in `test_public_endpoints.py` and `test_auth_wiring.py`.

- [ ] **Step 1: Read existing route test patterns**

```bash
cat tests/test_public_endpoints.py
cat tests/test_auth_wiring.py
```

Understand how the app fixture, session mocking, and workspace setup work.

- [ ] **Step 2: Write evidence route tests**

Create `tests/test_evidence_routes.py`:

```python
"""Tests for evidence API routes."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_workspace():
    ws = MagicMock()
    ws.id = uuid.uuid4()
    return ws


def test_create_evidence_source_requires_auth(client):
    """POST /v1/evidence/sources should require authentication."""
    response = client.post("/v1/evidence/sources", json={
        "source_kind": "BOOK",
        "title": "Test Source",
    })
    assert response.status_code == 401


def test_create_evidence_span_requires_auth(client):
    """POST /v1/evidence/spans should require authentication."""
    response = client.post("/v1/evidence/spans", json={
        "source_id": str(uuid.uuid4()),
        "start_char": 0,
        "end_char": 100,
        "excerpt": "test",
    })
    assert response.status_code == 401


def test_attach_edge_citation_requires_auth(client):
    """POST /v1/evidence/edge_citations should require authentication."""
    response = client.post("/v1/evidence/edge_citations", json={
        "edge_id": str(uuid.uuid4()),
        "evidence_span_id": str(uuid.uuid4()),
    })
    assert response.status_code == 401


def test_list_citations_requires_auth(client):
    """GET citations should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.get(f"/v1/objects/{oid}/versions/{vid}/citations")
    assert response.status_code == 401
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_evidence_routes.py -v
```
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_evidence_routes.py
git commit -m "test: add evidence route tests (auth enforcement)"
```

---

### Task 12: Review Route Tests

**Files:**
- Create: `tests/test_review_routes.py`

- [ ] **Step 1: Write review route tests**

Create `tests/test_review_routes.py`:

```python
"""Tests for review API routes."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from capability_commons.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_submit_review_requires_auth(client):
    """POST /v1/reviews should require authentication."""
    response = client.post("/v1/reviews", json={
        "context_object_version_id": str(uuid.uuid4()),
        "review_type": "TECHNICAL",
        "outcome": "APPROVED",
    })
    assert response.status_code == 401


def test_open_contradiction_requires_auth(client):
    """POST /v1/contradictions should require authentication."""
    response = client.post("/v1/contradictions", json={
        "left_version_id": str(uuid.uuid4()),
        "right_version_id": str(uuid.uuid4()),
        "dimension": "FACTUAL",
        "severity": "MEDIUM",
    })
    assert response.status_code == 401


def test_resolve_contradiction_requires_auth(client):
    """POST /v1/contradictions/{id}/resolve should require authentication."""
    response = client.post(f"/v1/contradictions/{uuid.uuid4()}/resolve", json={
        "resolution_note": "Resolved",
    })
    assert response.status_code == 401


def test_verify_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/verify should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/verify")
    assert response.status_code == 401


def test_dispute_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/dispute should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/dispute")
    assert response.status_code == 401


def test_deprecate_version_requires_auth(client):
    """POST /v1/objects/{id}/versions/{vid}/deprecate should require authentication."""
    oid = uuid.uuid4()
    vid = uuid.uuid4()
    response = client.post(f"/v1/objects/{oid}/versions/{vid}/deprecate")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_review_routes.py -v
```
Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_review_routes.py
git commit -m "test: add review route tests (auth enforcement for all endpoints)"
```

---

## Summary

After completing all 12 tasks, the production-hardening work delivers:

| Area | Before | After |
|------|--------|-------|
| CI/CD | None | GitHub Actions: lint, test, typecheck, Docker build, integration |
| Logging | Basic format strings | structlog with JSON in production |
| Error tracking | None | Sentry (opt-in via DSN) |
| Metrics | None | Prometheus at `/metrics` |
| DB pooling | SQLAlchemy defaults | Configurable pool_size, max_overflow, recycle |
| Migration check | None | Startup warning for pending migrations |
| Health depth | DB only | DB + migration version + embedding status |
| Key rotation | No expiry | expire_at column, rotate CLI, TTL support |
| Swagger | Disabled | `/docs` and `/redoc` enabled |
| Type checking | None | mypy + ruff configured |
| Test coverage | 115 tests | ~130 tests (evidence + review routes) |

**Remaining operational items** (not code-addressable in this plan):
- Secrets management (Vault/SSM — deployment decision)
- HTTPS enforcement (reverse proxy config)
- Backup strategy (pg_dump cron)
- Staging/production config separation
- First real ingestion run
