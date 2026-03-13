# v1.0 Production Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all operational infrastructure gaps to make Capability Commons production-ready: entity merge, auth, pagination, rate limiting, outbox consumer, embedding pipeline, and integration tests.

**Architecture:** Postgres-only infrastructure (no Redis/Celery). API key auth via hashed keys in a new table. Async outbox worker as a separate process. Pluggable embedding provider with OpenAI default. Keyset cursor pagination on list/search endpoints.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Alembic, OpenAI API, pytest with real DB fixtures

---

### Task 1: Complete Entity Merge — Remap Downstream Relations

**Files:**
- Modify: `src/capability_commons/services/entities.py`
- Create: `tests/test_entity_merge.py`

**Step 1: Write the failing test**

```python
# tests/test_entity_merge.py
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from capability_commons.services.entities import EntityService
from capability_commons.domain.enums import EntityStatus


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_merge_remaps_aliases(mock_session):
    source_id = uuid.uuid4()
    target_id = uuid.uuid4()
    source = MagicMock(id=source_id, status=EntityStatus.ACTIVE)
    target = MagicMock(id=target_id, status=EntityStatus.ACTIVE)

    mock_session.get.side_effect = [source, target]
    # Mock execute to return empty results for the UPDATE queries
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    service = EntityService(mock_session)

    with patch("capability_commons.services.entities.get_entity") as mock_get:
        mock_get.side_effect = [source, target]
        with patch("capability_commons.services.entities.add_outbox_event", new_callable=AsyncMock):
            result = await service.merge_entities(source_id, target_id)

    assert source.status == EntityStatus.MERGED
    # Verify UPDATE statements were executed for remapping
    assert mock_session.execute.call_count >= 2  # aliases + object_links remapped
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_entity_merge.py -v`
Expected: FAIL (execute call_count assertion fails — current code doesn't remap)

**Step 3: Implement entity merge remapping**

Replace the `merge_entities` method in `src/capability_commons/services/entities.py`:

```python
async def merge_entities(self, source_entity_id: uuid.UUID, target_entity_id: uuid.UUID) -> Entity:
    if source_entity_id == target_entity_id:
        raise ConflictError("Source and target entity must differ")
    source = await get_entity(self.session, source_entity_id)
    target = await get_entity(self.session, target_entity_id)

    # Remap aliases from source to target
    await self.session.execute(
        update(EntityAlias)
        .where(EntityAlias.entity_id == source_entity_id)
        .values(entity_id=target_entity_id)
    )

    # Remap context_object_entities from source to target
    # Delete any that would create duplicates first
    await self.session.execute(
        delete(ContextObjectEntity).where(
            ContextObjectEntity.entity_id == source_entity_id,
            ContextObjectEntity.context_object_version_id.in_(
                select(ContextObjectEntity.context_object_version_id).where(
                    ContextObjectEntity.entity_id == target_entity_id
                )
            ),
        )
    )
    await self.session.execute(
        update(ContextObjectEntity)
        .where(ContextObjectEntity.entity_id == source_entity_id)
        .values(entity_id=target_entity_id)
    )

    # Remap edges where source entity is src or dst
    await self.session.execute(
        update(Edge)
        .where(Edge.src_id == source_entity_id, Edge.src_node_kind == NodeKind.ENTITY)
        .values(src_id=target_entity_id)
    )
    await self.session.execute(
        update(Edge)
        .where(Edge.dst_id == source_entity_id, Edge.dst_node_kind == NodeKind.ENTITY)
        .values(dst_id=target_entity_id)
    )

    source.status = EntityStatus.MERGED
    await add_outbox_event(
        self.session,
        aggregate_type="entity",
        aggregate_id=target.id,
        event_type="entity.merged",
        payload={"source_entity_id": str(source.id), "target_entity_id": str(target.id)},
    )
    await self.session.commit()
    await self.session.refresh(target)
    return target
```

Add these imports at the top of `entities.py`:

```python
from sqlalchemy import delete, select, update
from capability_commons.db.models import ContextObjectEntity, Edge, Entity, EntityAlias
from capability_commons.domain.enums import EntityStatus, EntityType, NodeKind
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_entity_merge.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capability_commons/services/entities.py tests/test_entity_merge.py
git commit -m "feat: complete entity merge with downstream relation remapping"
```

---

### Task 2: API Key Auth — Migration and Model

**Files:**
- Create: `alembic/versions/20260313_0002_api_keys.py`
- Modify: `src/capability_commons/db/models.py`
- Modify: `src/capability_commons/config.py`

**Step 1: Add ApiKey model to models.py**

Add after the `Workspace` class:

```python
class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_key_hash", "key_hash", unique=True),
        Index("idx_api_keys_workspace", "workspace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(lazy="selectin")
```

**Step 2: Create the Alembic migration**

```python
# alembic/versions/20260313_0002_api_keys.py
"""Add api_keys table and rate_limit_log table

Revision ID: 0002
Revises: (previous revision ID)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = None  # Will be set to actual previous revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("idx_api_keys_workspace", "api_keys", ["workspace_id"])

    op.create_table(
        "rate_limit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("key_hash", "window_start", name="uq_rate_limit_key_window"),
    )
    op.create_index("idx_rate_limit_log_window", "rate_limit_log", ["window_start"])


def downgrade() -> None:
    op.drop_table("rate_limit_log")
    op.drop_table("api_keys")
```

**Step 3: Add auth config vars**

Add to `Settings` in `src/capability_commons/config.py`:

```python
# Auth
auth_enabled: bool = True
rate_limit_per_minute: int = 100
rate_limit_public_per_minute: int = 300

# Embeddings
openai_api_key: str = ""
embedding_model: str = "text-embedding-3-small"
embedding_batch_size: int = 50

# Worker
outbox_poll_interval_seconds: float = 2.0
```

**Step 4: Run migration**

Run: `source .venv/bin/activate && alembic upgrade head`

**Step 5: Commit**

```bash
git add src/capability_commons/db/models.py src/capability_commons/config.py alembic/versions/20260313_0002_api_keys.py
git commit -m "feat: add api_keys and rate_limit_log tables, auth/embedding config"
```

---

### Task 3: API Key Auth — Middleware and Dependencies

**Files:**
- Modify: `src/capability_commons/api/deps.py`
- Modify: `src/capability_commons/main.py`
- Create: `src/capability_commons/api/auth.py`
- Create: `tests/test_auth.py`

**Step 1: Create auth module**

```python
# src/capability_commons/api/auth.py
from __future__ import annotations

import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ApiKey, Workspace


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """Returns (raw_key, key_hash)."""
    raw = f"cc_{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw)


async def resolve_api_key(session: AsyncSession, raw_key: str) -> tuple[ApiKey, Workspace] | None:
    key_hash = hash_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    workspace = await session.get(Workspace, api_key.workspace_id)
    if workspace is None:
        return None
    return api_key, workspace
```

**Step 2: Update deps.py**

Replace the contents of `src/capability_commons/api/deps.py`:

```python
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.db.session import get_session

from sqlalchemy.ext.asyncio import AsyncSession


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return uuid.UUID(value)


async def get_actor_id(x_actor_id: Annotated[str | None, Header()] = None) -> uuid.UUID | None:
    return _parse_uuid(x_actor_id)


async def get_current_workspace(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> Workspace:
    settings = get_settings()
    if not settings.auth_enabled:
        # In dev mode without auth, use X-Workspace-Id header or raise
        ws_id = request.headers.get("x-workspace-id")
        if ws_id is None:
            raise HTTPException(status_code=401, detail="Missing X-Workspace-Id header (auth disabled)")
        ws = await session.get(Workspace, uuid.UUID(ws_id))
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_key = authorization[7:]  # Strip "Bearer "
    from capability_commons.api.auth import resolve_api_key

    result = await resolve_api_key(session, raw_key)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    api_key, workspace = result

    # Store key_hash on request state for rate limiting
    request.state.api_key_hash = api_key.key_hash
    return workspace


DBSession = Annotated[AsyncSession, Depends(get_db)]
ActorID = Annotated[uuid.UUID | None, Depends(get_actor_id)]
CurrentWorkspace = Annotated[Workspace, Depends(get_current_workspace)]
```

**Step 3: Write test**

```python
# tests/test_auth.py
from capability_commons.api.auth import generate_key, hash_key


def test_generate_key_format():
    raw, hashed = generate_key()
    assert raw.startswith("cc_")
    assert len(raw) > 30
    assert hashed == hash_key(raw)


def test_hash_key_deterministic():
    assert hash_key("test123") == hash_key("test123")
    assert hash_key("test123") != hash_key("test456")
```

**Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/capability_commons/api/auth.py src/capability_commons/api/deps.py tests/test_auth.py
git commit -m "feat: add API key auth middleware and workspace resolution"
```

---

### Task 4: API Key CLI — Create and Revoke Keys

**Files:**
- Create: `src/capability_commons/cli/keys.py`

**Step 1: Write the CLI**

```python
# src/capability_commons/cli/keys.py
"""CLI for managing API keys."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.api.auth import generate_key
from capability_commons.db.models import ApiKey, Workspace


async def create_key(db_url: str, workspace_slug: str, name: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.slug == workspace_slug)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            print(f"ERROR: workspace '{workspace_slug}' not found")
            await engine.dispose()
            return

        raw_key, key_hash = generate_key()
        api_key = ApiKey(
            workspace_id=ws.id,
            key_hash=key_hash,
            name=name,
        )
        session.add(api_key)
        await session.commit()

    await engine.dispose()
    print(f"API key created for workspace '{workspace_slug}':")
    print(f"  Name: {name}")
    print(f"  Key:  {raw_key}")
    print(f"  ID:   {api_key.id}")
    print()
    print("Store this key securely — it cannot be retrieved again.")


async def revoke_key(db_url: str, key_id: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        api_key = await session.get(ApiKey, uuid.UUID(key_id))
        if api_key is None:
            print(f"ERROR: API key '{key_id}' not found")
            await engine.dispose()
            return
        if api_key.revoked_at is not None:
            print(f"API key '{key_id}' is already revoked")
            await engine.dispose()
            return

        api_key.revoked_at = datetime.now(timezone.utc)
        await session.commit()

    await engine.dispose()
    print(f"API key '{key_id}' revoked successfully")


async def list_keys(db_url: str, workspace_slug: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.slug == workspace_slug)
        )
        ws = result.scalar_one_or_none()
        if ws is None:
            print(f"ERROR: workspace '{workspace_slug}' not found")
            await engine.dispose()
            return

        result = await session.execute(
            select(ApiKey).where(ApiKey.workspace_id == ws.id).order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()

    await engine.dispose()

    if not keys:
        print(f"No API keys for workspace '{workspace_slug}'")
        return

    print(f"API keys for workspace '{workspace_slug}':")
    for k in keys:
        status = "REVOKED" if k.revoked_at else "ACTIVE"
        print(f"  [{status}] {k.id}  {k.name}  (created {k.created_at.date()})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Manage API keys")
    sub = parser.add_subparsers(dest="command")

    create_p = sub.add_parser("create")
    create_p.add_argument("--workspace", required=True, help="Workspace slug")
    create_p.add_argument("--name", required=True, help="Key name/description")
    create_p.add_argument("--db-url", default=None)

    revoke_p = sub.add_parser("revoke")
    revoke_p.add_argument("--key-id", required=True, help="API key UUID to revoke")
    revoke_p.add_argument("--db-url", default=None)

    list_p = sub.add_parser("list")
    list_p.add_argument("--workspace", required=True, help="Workspace slug")
    list_p.add_argument("--db-url", default=None)

    args = parser.parse_args()

    if args.db_url is None:
        from capability_commons.config import get_settings
        db_url = get_settings().database_url
    else:
        db_url = args.db_url

    if args.command == "create":
        asyncio.run(create_key(db_url, args.workspace, args.name))
    elif args.command == "revoke":
        asyncio.run(revoke_key(db_url, args.key_id))
    elif args.command == "list":
        asyncio.run(list_keys(db_url, args.workspace))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 2: Test manually**

Run: `source .venv/bin/activate && python -m capability_commons.cli.keys create --workspace capability-commons --name "dev-key"`
Expected: prints new API key

**Step 3: Commit**

```bash
git add src/capability_commons/cli/keys.py
git commit -m "feat: add CLI for creating, revoking, and listing API keys"
```

---

### Task 5: Cursor Pagination

**Files:**
- Create: `src/capability_commons/schemas/pagination.py`
- Modify: `src/capability_commons/api/routes/objects.py`
- Modify: `src/capability_commons/api/routes/search.py`
- Modify: `src/capability_commons/services/registry.py`
- Create: `tests/test_pagination.py`

**Step 1: Create pagination schemas**

```python
# src/capability_commons/schemas/pagination.py
from __future__ import annotations

import base64
import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    cursor: str | None = Field(None, description="Opaque cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Max items to return")

    def decode_cursor(self) -> uuid.UUID | None:
        if self.cursor is None:
            return None
        try:
            raw = base64.urlsafe_b64decode(self.cursor.encode()).decode()
            return uuid.UUID(raw)
        except (ValueError, Exception):
            return None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total_count: int

    @staticmethod
    def encode_cursor(item_id: uuid.UUID) -> str:
        return base64.urlsafe_b64encode(str(item_id).encode()).decode()
```

**Step 2: Write test**

```python
# tests/test_pagination.py
import uuid

from capability_commons.schemas.pagination import PaginatedResponse, PaginationParams


def test_cursor_encode_decode():
    item_id = uuid.uuid4()
    cursor = PaginatedResponse.encode_cursor(item_id)
    params = PaginationParams(cursor=cursor, limit=10)
    decoded = params.decode_cursor()
    assert decoded == item_id


def test_cursor_none():
    params = PaginationParams(limit=10)
    assert params.decode_cursor() is None


def test_limit_bounds():
    p = PaginationParams(limit=1)
    assert p.limit == 1
    p = PaginationParams(limit=100)
    assert p.limit == 100
```

**Step 3: Add list_objects to RegistryService**

Add to `src/capability_commons/services/registry.py`:

```python
async def list_objects(
    self,
    workspace_id: uuid.UUID,
    *,
    cursor_id: uuid.UUID | None = None,
    limit: int = 20,
) -> tuple[list[ContextObject], int]:
    count_stmt = select(func.count(ContextObject.id)).where(
        ContextObject.workspace_id == workspace_id
    )
    total = (await self.session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(ContextObject)
        .where(ContextObject.workspace_id == workspace_id)
        .order_by(ContextObject.created_at.desc(), ContextObject.id.desc())
        .limit(limit + 1)
    )
    if cursor_id is not None:
        cursor_obj = await self.session.get(ContextObject, cursor_id)
        if cursor_obj is not None:
            stmt = stmt.where(
                (ContextObject.created_at < cursor_obj.created_at)
                | (
                    (ContextObject.created_at == cursor_obj.created_at)
                    & (ContextObject.id < cursor_id)
                )
            )

    result = await self.session.execute(stmt)
    objects = list(result.scalars().all())
    return objects, total
```

**Step 4: Add GET /objects list endpoint**

Add to `src/capability_commons/api/routes/objects.py`:

```python
@router.get("/objects", response_model=PaginatedResponse[ObjectResponse])
async def list_objects(
    workspace_id: uuid.UUID,
    session: DBSession,
    cursor: str | None = None,
    limit: int = 20,
) -> PaginatedResponse[ObjectResponse]:
    from capability_commons.schemas.pagination import PaginatedResponse, PaginationParams
    params = PaginationParams(cursor=cursor, limit=min(limit, 100))
    service = RegistryService(session)
    objects, total = await service.list_objects(
        workspace_id, cursor_id=params.decode_cursor(), limit=params.limit,
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

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_pagination.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capability_commons/schemas/pagination.py src/capability_commons/api/routes/objects.py src/capability_commons/services/registry.py tests/test_pagination.py
git commit -m "feat: add cursor pagination with keyset strategy"
```

---

### Task 6: Rate Limiting Middleware

**Files:**
- Create: `src/capability_commons/api/rate_limit.py`
- Modify: `src/capability_commons/db/models.py`
- Modify: `src/capability_commons/main.py`
- Create: `tests/test_rate_limit.py`

**Step 1: Add RateLimitLog model**

Add to `src/capability_commons/db/models.py` after `OutboxEvent`:

```python
class RateLimitLog(Base):
    __tablename__ = "rate_limit_log"
    __table_args__ = (
        UniqueConstraint("key_hash", "window_start", name="uq_rate_limit_key_window"),
        Index("idx_rate_limit_log_window", "window_start"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
```

**Step 2: Create rate limiter**

```python
# src/capability_commons/api/rate_limit.py
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sqlalchemy import select, text as sa_text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.config import get_settings
from capability_commons.db.models import RateLimitLog


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_factory: async_sessionmaker):
        super().__init__(app)
        self.session_factory = session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Skip rate limiting if auth is disabled
        if not settings.auth_enabled:
            return await call_next(request)

        # Determine key: API key hash if authenticated, or IP for public routes
        is_public = request.url.path.startswith("/v1/public/") or request.url.path == "/health"
        key_hash = getattr(request.state, "api_key_hash", None)

        if key_hash is None and not is_public:
            # No key and not public — auth middleware will handle rejection
            return await call_next(request)

        if key_hash is None:
            # Public route — rate limit by IP
            client_ip = request.client.host if request.client else "unknown"
            key_hash = f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
            limit = settings.rate_limit_public_per_minute
        else:
            limit = settings.rate_limit_per_minute

        # Current minute window
        now = datetime.now(timezone.utc)
        window_start = now.replace(second=0, microsecond=0)

        async with self.session_factory() as session:
            # Upsert with increment
            stmt = pg_insert(RateLimitLog).values(
                key_hash=key_hash,
                window_start=window_start,
                request_count=1,
            ).on_conflict_do_update(
                constraint="uq_rate_limit_key_window",
                set_={"request_count": RateLimitLog.request_count + 1},
            ).returning(RateLimitLog.request_count)

            result = await session.execute(stmt)
            count = result.scalar_one()
            await session.commit()

        if count > limit:
            retry_after = 60 - now.second
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
```

**Step 3: Wire into main.py**

Add after CORS middleware in `src/capability_commons/main.py`:

```python
from capability_commons.db.session import SessionLocal
from capability_commons.api.rate_limit import RateLimitMiddleware

# ... after register_error_handlers(app)
app.add_middleware(RateLimitMiddleware, session_factory=SessionLocal)
```

**Step 4: Write test**

```python
# tests/test_rate_limit.py
import hashlib
from datetime import datetime, timezone

from capability_commons.api.rate_limit import RateLimitMiddleware


def test_ip_hash_consistency():
    ip = "192.168.1.1"
    h1 = f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    h2 = f"ip:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    assert h1 == h2


def test_window_truncation():
    now = datetime(2026, 3, 13, 12, 34, 56, 789, tzinfo=timezone.utc)
    window = now.replace(second=0, microsecond=0)
    assert window.second == 0
    assert window.microsecond == 0
    assert window.minute == 34
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_rate_limit.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capability_commons/api/rate_limit.py src/capability_commons/db/models.py src/capability_commons/main.py tests/test_rate_limit.py
git commit -m "feat: add sliding-window rate limiting middleware"
```

---

### Task 7: Outbox Event Consumer

**Files:**
- Create: `src/capability_commons/cli/worker.py`
- Create: `tests/test_worker.py`

**Step 1: Write the worker**

```python
# src/capability_commons/cli/worker.py
"""Outbox event consumer — polls for unprocessed events and dispatches handlers."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.db.models import OutboxEvent

logger = logging.getLogger(__name__)

# Event type → handler function name
HANDLERS: dict[str, str] = {
    "version.published": "_handle_version_published",
    "version.reindexed": "_handle_version_reindexed",
}


class OutboxWorker:
    def __init__(self, db_url: str, poll_interval: float = 2.0) -> None:
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(bind=self.engine, expire_on_commit=False)
        self.poll_interval = poll_interval
        self._running = True

    async def run(self) -> None:
        logger.info("Outbox worker started (poll_interval=%.1fs)", self.poll_interval)
        while self._running:
            processed = await self._poll_batch()
            if processed == 0:
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        await self.engine.dispose()

    async def _poll_batch(self, batch_size: int = 50) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.processed_at.is_(None))
                .order_by(OutboxEvent.id.asc())
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
            events = list(result.scalars().all())

            if not events:
                return 0

            for event in events:
                try:
                    await self._dispatch(session, event)
                except Exception:
                    logger.exception("Failed to process event %d (%s)", event.id, event.event_type)

                event.processed_at = datetime.now(timezone.utc)

            await session.commit()
            logger.info("Processed %d outbox events", len(events))
            return len(events)

    async def _dispatch(self, session, event: OutboxEvent) -> None:
        handler_name = HANDLERS.get(event.event_type)
        if handler_name is None:
            return  # No handler for this event type — mark processed and move on

        handler = getattr(self, handler_name)
        await handler(session, event)

    async def _handle_version_published(self, session, event: OutboxEvent) -> None:
        """Reindex the published version for search."""
        import uuid
        from capability_commons.search.indexer import VersionIndexer

        version_id = uuid.UUID(event.payload.get("version_id", str(event.aggregate_id)))
        indexer = VersionIndexer(session)
        segments = await indexer.reindex_version(version_id)
        logger.info("Reindexed version %s (%d segments)", version_id, len(segments))

    async def _handle_version_reindexed(self, session, event: OutboxEvent) -> None:
        """Generate embeddings for reindexed segments."""
        import uuid
        from capability_commons.config import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            logger.debug("No OPENAI_API_KEY configured, skipping embedding generation")
            return

        version_id = uuid.UUID(event.payload.get("version_id", str(event.aggregate_id)))
        from capability_commons.services.embedding import EmbeddingService
        embedding_svc = EmbeddingService(session)
        count = await embedding_svc.embed_version(version_id)
        logger.info("Generated embeddings for version %s (%d segments)", version_id, count)


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run the outbox event worker")
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--poll-interval", type=float, default=None)
    args = parser.parse_args()

    from capability_commons.config import get_settings
    settings = get_settings()

    db_url = args.db_url or settings.database_url
    poll_interval = args.poll_interval or settings.outbox_poll_interval_seconds

    worker = OutboxWorker(db_url, poll_interval)

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        asyncio.run(worker.stop())
        print("Worker stopped")


if __name__ == "__main__":
    main()
```

**Step 2: Write test**

```python
# tests/test_worker.py
from capability_commons.cli.worker import HANDLERS, OutboxWorker


def test_handler_registry():
    assert "version.published" in HANDLERS
    assert "version.reindexed" in HANDLERS


def test_worker_has_handlers():
    worker = OutboxWorker.__new__(OutboxWorker)
    for handler_name in HANDLERS.values():
        assert hasattr(worker, handler_name), f"Missing handler: {handler_name}"
```

**Step 3: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_worker.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/capability_commons/cli/worker.py tests/test_worker.py
git commit -m "feat: add outbox event consumer with reindex and embedding triggers"
```

---

### Task 8: Embedding Pipeline — Provider Interface and OpenAI Adapter

**Files:**
- Create: `src/capability_commons/services/embedding.py`
- Modify: `src/capability_commons/search/adapters/postgres_search.py`
- Modify: `pyproject.toml`
- Create: `tests/test_embedding.py`

**Step 1: Add openai dependency**

Add `"openai>=1.0,<2.0"` to the dependencies list in `pyproject.toml`.

Run: `source .venv/bin/activate && pip install -e ".[dev]"`

**Step 2: Create embedding service**

```python
# src/capability_commons/services/embedding.py
"""Embedding pipeline: pluggable provider with OpenAI default."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContentSegment


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int = 1536) -> None:
        self.model = model
        self.dimensions = dimensions
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in response.data]


class EmbeddingService:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        if provider is None:
            from capability_commons.config import get_settings
            settings = get_settings()
            if settings.openai_api_key:
                self.provider = OpenAIEmbeddingProvider(
                    api_key=settings.openai_api_key,
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dim,
                )
            else:
                self.provider = None
        else:
            self.provider = provider

    async def embed_version(self, version_id: uuid.UUID, batch_size: int = 50) -> int:
        if self.provider is None:
            return 0

        result = await self.session.execute(
            select(ContentSegment)
            .where(
                ContentSegment.context_object_version_id == version_id,
                ContentSegment.embedding.is_(None),
            )
            .order_by(ContentSegment.ordinal.asc())
        )
        segments = list(result.scalars().all())

        if not segments:
            return 0

        count = 0
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            texts = [seg.text_content for seg in batch]
            embeddings = await self.provider.embed(texts)
            for seg, emb in zip(batch, embeddings):
                seg.embedding = emb
                seg.metadata_json = {**seg.metadata_json, "embedding_status": "complete"}
            count += len(batch)

        await self.session.flush()
        await self.session.commit()
        return count
```

**Step 3: Add hybrid search to PostgresSearchAdapter**

Add a `_hybrid_search` path to `search()` in `src/capability_commons/search/adapters/postgres_search.py`. Modify the `search` method to check if embeddings are available and blend scores:

After the existing FTS query builds the result, add vector scoring. Replace the `search` method with one that supports hybrid mode. The key addition is: if a query embedding can be computed and segments have embeddings, compute cosine similarity and blend with FTS rank.

For now, add a simpler approach — a `search_hybrid` method that can be called when embeddings are available, leaving the existing `search` method unchanged:

```python
async def search_hybrid(
    self,
    *,
    workspace_id,
    query,
    query_embedding: list[float] | None,
    filters,
    top_k,
    object_types=None,
    only_published=True,
    fts_weight: float = 0.7,
    vector_weight: float = 0.3,
) -> list[SearchHit]:
    """FTS + vector cosine similarity hybrid search."""
    if query_embedding is None:
        return await self.search(
            workspace_id=workspace_id,
            query=query,
            filters=filters,
            top_k=top_k,
            object_types=object_types,
            only_published=only_published,
        )

    # Get FTS hits (expanded pool)
    fts_hits = await self.search(
        workspace_id=workspace_id,
        query=query,
        filters=filters,
        top_k=top_k * 3,
        object_types=object_types,
        only_published=only_published,
    )

    if not fts_hits:
        return []

    # Get vector scores for the FTS hit versions
    version_ids = [h.version_id for h in fts_hits]
    result = await self.session.execute(
        select(
            ContentSegment.context_object_version_id,
            func.max(
                1 - ContentSegment.embedding.cosine_distance(query_embedding)
            ).label("vector_score"),
        )
        .where(
            ContentSegment.context_object_version_id.in_(version_ids),
            ContentSegment.embedding.is_not(None),
        )
        .group_by(ContentSegment.context_object_version_id)
    )
    vector_scores = {row[0]: float(row[1]) for row in result.all()}

    # Blend scores
    max_fts = max(h.score for h in fts_hits) or 1.0
    for hit in fts_hits:
        norm_fts = hit.score / max_fts
        vec_score = vector_scores.get(hit.version_id, 0.0)
        hit.score = (fts_weight * norm_fts) + (vector_weight * vec_score)

    fts_hits.sort(key=lambda h: h.score, reverse=True)
    return fts_hits[:top_k]
```

**Step 4: Write test**

```python
# tests/test_embedding.py
import pytest
from unittest.mock import AsyncMock

from capability_commons.services.embedding import EmbeddingProvider, EmbeddingService


class FakeProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 10 for _ in texts]


@pytest.mark.asyncio
async def test_embed_version_no_provider():
    session = AsyncMock()
    service = EmbeddingService(session, provider=None)
    result = await service.embed_version("fake-id")
    assert result == 0


def test_fake_provider_returns_correct_count():
    import asyncio
    provider = FakeProvider()
    result = asyncio.run(provider.embed(["hello", "world"]))
    assert len(result) == 2
    assert len(result[0]) == 10
```

**Step 5: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_embedding.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/capability_commons/services/embedding.py src/capability_commons/search/adapters/postgres_search.py pyproject.toml tests/test_embedding.py
git commit -m "feat: add embedding pipeline with OpenAI provider and hybrid search"
```

---

### Task 9: Integration Tests — Core Flows

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_integration.py`

**Step 1: Create test fixtures**

```python
# tests/conftest.py
from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.domain.enums import WorkspaceVisibility


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

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
    return ws
```

**Step 2: Write integration tests**

```python
# tests/test_integration.py
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
    """Create object → create version → publish → verify state."""
    service = RegistryService(db_session)

    # Create object
    req = CreateObjectRequest(
        workspace_id=workspace.id,
        slug="test-skill",
        type=COType.SKILL_GUIDE,
        title="Test Skill",
    )
    obj = await service.create_object(req)
    assert obj.lifecycle_state == LifecycleState.DRAFT

    # Create version
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

    # Publish
    published_obj = await service.publish_version(obj.id, version.id)
    assert published_obj.lifecycle_state == LifecycleState.PUBLISHED
    assert published_obj.current_version_id == version.id


@pytest.mark.asyncio
async def test_edge_creation(db_session, workspace):
    """Create two objects and link them with an edge."""
    service = RegistryService(db_session)

    obj_a = await service.create_object(CreateObjectRequest(
        workspace_id=workspace.id, slug="node-a", type=COType.CONCEPT_NOTE, title="Node A",
    ))
    ver_a = await service.create_version(obj_a.id, CreateVersionRequest(
        title="Node A v1", plain_language="Node A.", markdown_body="Body A.",
        structured_data={"definition": "A concept."},
    ))

    obj_b = await service.create_object(CreateObjectRequest(
        workspace_id=workspace.id, slug="node-b", type=COType.CONCEPT_NOTE, title="Node B",
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
        workspace_id=workspace.id, slug="faceted", type=COType.SKILL_GUIDE, title="Faceted",
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
        {"facet_type": FacetType.DOMAIN, "facet_value": "water"},
        {"facet_type": FacetType.AUDIENCE, "facet_value": "general"},
    ])

    refreshed = await service.get_version(version.id)
    facet_types = [f.facet_type for f in refreshed.facets]
    assert FacetType.DOMAIN in facet_types
    assert FacetType.AUDIENCE in facet_types
```

**Step 3: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_integration.py -v`
Expected: All 3 tests pass

**Step 4: Commit**

```bash
git add tests/conftest.py tests/test_integration.py
git commit -m "test: add integration tests for object lifecycle, edges, and facets"
```

---

## Completion Checklist

- [ ] Entity merge remaps aliases, object links, and edges
- [ ] ApiKey model + migration
- [ ] Auth middleware resolves API key → workspace
- [ ] CLI to create/revoke/list API keys
- [ ] Cursor pagination schemas + list objects endpoint
- [ ] Rate limiting middleware with sliding window
- [ ] Outbox event consumer with reindex + embedding triggers
- [ ] Embedding provider interface + OpenAI adapter
- [ ] Hybrid FTS + vector search
- [ ] Integration tests for object lifecycle, edges, facets
- [ ] All unit tests passing
