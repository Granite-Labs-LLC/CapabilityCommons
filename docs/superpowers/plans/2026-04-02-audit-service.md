# Audit Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an append-only audit event log for all significant state changes (object creates, publishes, edge creates, reviews) to enable transparent governance history.

**Architecture:** New `AuditEventType` enum, `AuditEvent` ORM model, Alembic migration, `AuditService` with record/query methods, API routes for timeline queries, and integration calls from `RegistryService` and `ReviewService`.

**Tech Stack:** SQLAlchemy 2 async, Alembic, FastAPI, Pydantic v2, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/capability_commons/domain/enums.py` | Add `AuditEventType` enum |
| `src/capability_commons/db/models.py` | Add `AuditEvent` model |
| `alembic/versions/20260402_0001_audit_events.py` | Migration for audit_events table |
| `src/capability_commons/audit/service.py` | `AuditService` — record and query events |
| `src/capability_commons/schemas/audit.py` | Request/response schemas |
| `src/capability_commons/api/routes/audit.py` | GET endpoints for timeline queries |
| `src/capability_commons/api/router.py` | Wire audit routes |
| `src/capability_commons/services/registry.py` | Add audit calls after creates/publishes |
| `src/capability_commons/services/review.py` | Add audit call after review submission |
| `tests/test_audit.py` | Unit tests for enum, model, schema, route wiring |
| `tests/test_integration_audit.py` | Integration tests against real DB |

---

### Task 1: Add AuditEventType Enum

**Files:**
- Modify: `src/capability_commons/domain/enums.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit.py`:

```python
"""Tests for the audit service."""
from __future__ import annotations


def test_audit_event_type_enum():
    """AuditEventType enum should have all expected members."""
    from capability_commons.domain.enums import AuditEventType

    expected = {
        "object_created", "version_created", "version_published",
        "version_deprecated", "edge_created", "edge_removed",
        "review_submitted", "object_edited",
    }
    actual = {e.value for e in AuditEventType}
    assert actual == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit.py::test_audit_event_type_enum -v`
Expected: FAIL with `ImportError` or `AttributeError`

- [ ] **Step 3: Add the enum to enums.py**

Add at the end of `src/capability_commons/domain/enums.py`:

```python
class AuditEventType(StrEnum):
    OBJECT_CREATED = "object_created"
    VERSION_CREATED = "version_created"
    VERSION_PUBLISHED = "version_published"
    VERSION_DEPRECATED = "version_deprecated"
    EDGE_CREATED = "edge_created"
    EDGE_REMOVED = "edge_removed"
    REVIEW_SUBMITTED = "review_submitted"
    OBJECT_EDITED = "object_edited"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit.py::test_audit_event_type_enum -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/domain/enums.py tests/test_audit.py
git commit -m "feat(audit): add AuditEventType enum"
```

---

### Task 2: Add AuditEvent Model and Migration

**Files:**
- Modify: `src/capability_commons/db/models.py`
- Create: `alembic/versions/20260402_0001_audit_events.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit.py`:

```python
def test_audit_event_model_exists():
    """AuditEvent model should exist with expected columns."""
    from capability_commons.db.models import AuditEvent

    columns = {c.name for c in AuditEvent.__table__.columns}
    expected = {
        "id", "workspace_id", "event_type", "actor_key_id",
        "target_object_id", "target_version_id", "target_edge_id",
        "detail", "created_at",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit.py::test_audit_event_model_exists -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add the model to models.py**

Add to `src/capability_commons/db/models.py` imports:

```python
from capability_commons.domain.enums import AuditEventType  # add to existing enum imports
```

Add the model class (after the `Feedback` model):

```python
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    event_type: Mapped[AuditEventType] = mapped_column(SAEnum(AuditEventType, name="audit_event_type", create_type=False), nullable=False)
    actor_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)
    target_object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_objects.id"), nullable=True)
    target_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_object_versions.id"), nullable=True)
    target_edge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("edges.id"), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_audit_workspace_created", "workspace_id", created_at.desc()),
        Index("idx_audit_object_created", "target_object_id", created_at.desc()),
    )
```

- [ ] **Step 4: Create the Alembic migration**

Create `alembic/versions/20260402_0001_audit_events.py`:

```python
"""Add audit_events table.

Revision ID: 20260402_0001
Revises: 20260401_0001
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "20260402_0001"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit_event_type = sa.Enum(
        "object_created", "version_created", "version_published",
        "version_deprecated", "edge_created", "edge_removed",
        "review_submitted", "object_edited",
        name="audit_event_type",
    )
    audit_event_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column("actor_key_id", UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=True),
        sa.Column("target_object_id", UUID(as_uuid=True), sa.ForeignKey("context_objects.id"), nullable=True),
        sa.Column("target_version_id", UUID(as_uuid=True), sa.ForeignKey("context_object_versions.id"), nullable=True),
        sa.Column("target_edge_id", UUID(as_uuid=True), sa.ForeignKey("edges.id"), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_audit_workspace_created", "audit_events", ["workspace_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_object_created", "audit_events", ["target_object_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_audit_object_created", table_name="audit_events")
    op.drop_index("idx_audit_workspace_created", table_name="audit_events")
    op.drop_table("audit_events")
    sa.Enum(name="audit_event_type").drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_audit.py::test_audit_event_model_exists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/db/models.py alembic/versions/20260402_0001_audit_events.py tests/test_audit.py
git commit -m "feat(audit): add AuditEvent model and migration"
```

---

### Task 3: Add AuditService

**Files:**
- Create: `src/capability_commons/audit/service.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit.py`:

```python
def test_audit_service_exists():
    """AuditService should have record_event, get_object_history, get_workspace_timeline."""
    from capability_commons.audit.service import AuditService
    import inspect

    assert hasattr(AuditService, "record_event")
    assert hasattr(AuditService, "get_object_history")
    assert hasattr(AuditService, "get_workspace_timeline")

    sig = inspect.signature(AuditService.record_event)
    params = set(sig.parameters.keys())
    assert "event_type" in params
    assert "workspace_id" in params
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit.py::test_audit_service_exists -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write the service**

Create `src/capability_commons/audit/service.py`:

```python
"""Append-only audit event log for governance transparency."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import AuditEvent
from capability_commons.domain.enums import AuditEventType


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        *,
        event_type: AuditEventType,
        workspace_id: uuid.UUID,
        actor_key_id: uuid.UUID | None = None,
        target_object_id: uuid.UUID | None = None,
        target_version_id: uuid.UUID | None = None,
        target_edge_id: uuid.UUID | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_key_id=actor_key_id,
            target_object_id=target_object_id,
            target_version_id=target_version_id,
            target_edge_id=target_edge_id,
            detail=detail,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_object_history(
        self,
        object_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        result = await self.session.execute(
            select(AuditEvent)
            .where(AuditEvent.target_object_id == object_id)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_workspace_timeline(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        event_type: AuditEventType | None = None,
    ) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if event_type is not None:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit.py::test_audit_service_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/audit/service.py tests/test_audit.py
git commit -m "feat(audit): add AuditService with record/query methods"
```

---

### Task 4: Add Audit Schemas and API Routes

**Files:**
- Create: `src/capability_commons/schemas/audit.py`
- Create: `src/capability_commons/api/routes/audit.py`
- Modify: `src/capability_commons/api/router.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_audit.py`:

```python
def test_audit_schemas():
    """Audit response schema should exist with expected fields."""
    from capability_commons.schemas.audit import AuditEventResponse

    fields = AuditEventResponse.model_fields
    assert "id" in fields
    assert "event_type" in fields
    assert "workspace_id" in fields
    assert "created_at" in fields
    assert "detail" in fields


def test_audit_routes_wired():
    """Audit routes should be wired in the API router."""
    from fastapi.testclient import TestClient
    from capability_commons.main import app

    client = TestClient(app)

    # Both should return 401 (auth required) not 404
    import uuid
    r = client.get(f"/v1/audit/objects/{uuid.uuid4()}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    r = client.get("/v1/audit/timeline")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audit.py::test_audit_schemas tests/test_audit.py::test_audit_routes_wired -v`
Expected: FAIL

- [ ] **Step 3: Create the schema**

Create `src/capability_commons/schemas/audit.py`:

```python
"""Schemas for audit event API responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from capability_commons.domain.enums import AuditEventType


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    event_type: AuditEventType
    actor_key_id: uuid.UUID | None = None
    target_object_id: uuid.UUID | None = None
    target_version_id: uuid.UUID | None = None
    target_edge_id: uuid.UUID | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create the route module**

Create `src/capability_commons/api/routes/audit.py`:

```python
"""Audit event API routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType
from capability_commons.schemas.audit import AuditEventResponse

router = APIRouter()


@router.get("/audit/objects/{object_id}", response_model=list[AuditEventResponse])
async def get_object_history(
    object_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = AuditService(session)
    events = await svc.get_object_history(object_id, limit=limit, offset=offset)
    return events


@router.get("/audit/timeline", response_model=list[AuditEventResponse])
async def get_workspace_timeline(
    session: DBSession,
    workspace: CurrentWorkspace,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: AuditEventType | None = Query(None),
):
    svc = AuditService(session)
    events = await svc.get_workspace_timeline(
        workspace.id, limit=limit, offset=offset, event_type=event_type,
    )
    return events
```

- [ ] **Step 5: Wire the routes in router.py**

Add to `src/capability_commons/api/router.py`:

Import: add `audit` to the imports from `capability_commons.api.routes`

Add line:
```python
api_router.include_router(audit.router, prefix="/v1", tags=["audit"])
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_audit.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/capability_commons/schemas/audit.py src/capability_commons/api/routes/audit.py src/capability_commons/api/router.py tests/test_audit.py
git commit -m "feat(audit): add audit schemas, API routes, and wire to router"
```

---

### Task 5: Integrate Audit Calls into RegistryService and ReviewService

**Files:**
- Modify: `src/capability_commons/services/registry.py`
- Modify: `src/capability_commons/services/review.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_audit.py`:

```python
def test_registry_service_imports_audit():
    """RegistryService should import and use AuditService."""
    import inspect
    from capability_commons.services import registry

    source = inspect.getsource(registry)
    assert "AuditService" in source, "RegistryService should reference AuditService"
    assert "record_event" in source, "RegistryService should call record_event"


def test_review_service_imports_audit():
    """ReviewService should import and use AuditService."""
    import inspect
    from capability_commons.services import review

    source = inspect.getsource(review)
    assert "AuditService" in source, "ReviewService should reference AuditService"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audit.py::test_registry_service_imports_audit tests/test_audit.py::test_review_service_imports_audit -v`
Expected: FAIL

- [ ] **Step 3: Add audit calls to RegistryService**

In `src/capability_commons/services/registry.py`:

Add import:
```python
from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType
```

In `create_object()`, after the `await self.session.flush()` and before `return obj`, add:
```python
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.OBJECT_CREATED,
            workspace_id=request.workspace_id,
            actor_key_id=actor_id,
            target_object_id=obj.id,
        )
```

In `create_version()`, after the version is flushed and before the return, add:
```python
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.VERSION_CREATED,
            workspace_id=obj.workspace_id,
            actor_key_id=actor_id,
            target_object_id=object_id,
            target_version_id=version.id,
        )
```

In `publish_version()`, after the state change flush and before the return, add:
```python
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.VERSION_PUBLISHED,
            workspace_id=obj.workspace_id,
            target_object_id=object_id,
            target_version_id=version_id,
        )
```

In `create_edge()`, after the `await self.session.flush()` and before `return edge`, add:
```python
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.EDGE_CREATED,
            workspace_id=workspace_id,
            actor_key_id=created_by,
            target_edge_id=edge.id,
        )
```

- [ ] **Step 4: Add audit call to ReviewService**

In `src/capability_commons/services/review.py`:

Add import:
```python
from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType
```

In `submit_review()`, after `self.session.add(review)` and `await self.session.flush()`, add:
```python
        audit = AuditService(self.session)
        await audit.record_event(
            event_type=AuditEventType.REVIEW_SUBMITTED,
            workspace_id=workspace_id,
            actor_key_id=reviewer_id,
            target_version_id=context_object_version_id,
            detail={"review_type": str(review_type), "outcome": str(outcome)},
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_audit.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Run existing tests to verify nothing broke**

Run: `pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_integration_embedding.py --ignore=tests/test_integration_publication.py --ignore=tests/test_integration_search.py --ignore=tests/test_integration_retrieval.py -v`
Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/capability_commons/services/registry.py src/capability_commons/services/review.py tests/test_audit.py
git commit -m "feat(audit): integrate audit calls into RegistryService and ReviewService"
```

---

### Task 6: Integration Tests for Audit Service

**Files:**
- Create: `tests/test_integration_audit.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the integration test file**

Create `tests/test_integration_audit.py`:

```python
"""Integration tests for the audit service against real Postgres."""
from __future__ import annotations

import uuid

import pytest

from capability_commons.audit.service import AuditService
from capability_commons.domain.enums import AuditEventType, COType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.services.registry import RegistryService


@pytest.mark.asyncio
async def test_create_object_emits_audit_event(db_session, workspace):
    """Creating an object should record an object_created audit event."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-audit-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Audit Test Object",
    ))
    await db_session.commit()

    events = await audit.get_object_history(obj.id)
    assert len(events) >= 1
    assert events[0].event_type == AuditEventType.OBJECT_CREATED
    assert events[0].target_object_id == obj.id


@pytest.mark.asyncio
async def test_publish_emits_audit_event(db_session, workspace):
    """Publishing a version should record a version_published audit event."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-audit-pub-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="Audit Publish Test",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Audit Publish v1",
        plain_language="Test.",
        markdown_body="# Test",
        structured_data={"definition": "Test."},
    ))
    await svc.publish_version(obj.id, ver.id)
    await db_session.commit()

    events = await audit.get_object_history(obj.id)
    event_types = [e.event_type for e in events]
    assert AuditEventType.OBJECT_CREATED in event_types
    assert AuditEventType.VERSION_CREATED in event_types
    assert AuditEventType.VERSION_PUBLISHED in event_types


@pytest.mark.asyncio
async def test_workspace_timeline(db_session, workspace):
    """get_workspace_timeline should return events across all objects."""
    svc = RegistryService(db_session)
    audit = AuditService(db_session)

    for i in range(3):
        await svc.create_object(CreateObjectRequest(
            workspace_id=workspace.id,
            slug=f"test-audit-tl-{i}-{uuid.uuid4().hex[:6]}",
            type=COType.CONCEPT_NOTE,
            canonical_title=f"Timeline Test {i}",
        ))
    await db_session.commit()

    timeline = await audit.get_workspace_timeline(workspace.id)
    assert len(timeline) >= 3

    # Filter by event type
    creates = await audit.get_workspace_timeline(
        workspace.id, event_type=AuditEventType.OBJECT_CREATED,
    )
    assert all(e.event_type == AuditEventType.OBJECT_CREATED for e in creates)
```

- [ ] **Step 2: Update CI to run audit integration tests**

In `.github/workflows/ci.yml`, add `tests/test_integration_audit.py` to both the ignore list (line ~39) and the integration run list (line ~66).

Unit test line:
```yaml
      - run: pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_integration_embedding.py --ignore=tests/test_integration_publication.py --ignore=tests/test_integration_search.py --ignore=tests/test_integration_retrieval.py --ignore=tests/test_integration_audit.py -v
```

Integration test line:
```yaml
      - run: pytest tests/test_integration.py tests/test_integration_embedding.py tests/test_integration_publication.py tests/test_integration_search.py tests/test_integration_retrieval.py tests/test_integration_audit.py -v
```

- [ ] **Step 3: Run integration tests (requires live Postgres)**

Run: `pytest tests/test_integration_audit.py -v`
Expected: 3 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_audit.py .github/workflows/ci.yml
git commit -m "test(audit): add integration tests and update CI"
```

---

### Task 7: Update Documentation

**Files:**
- Modify: `STATUS.md`
- Modify: `TODO.md`

- [ ] **Step 1: Update STATUS.md**

Add the audit route to the route module table:
```
| Audit | 2 (object history, timeline) | Production-ready |
```

Update the endpoint count from 49 to 51.
Update the table count from 24 to 25.
Update the migration count from 9 to 10.

In the services table, update the audit entry:
```
| `AuditService` | Append-only event log for governance transparency | Fully implemented |
```

- [ ] **Step 2: Update TODO.md**

Mark the audit service item as done:
```
- [x] **Implement audit service** — append-only event logging for object creates, edits, publishes, edge changes, and reviews. API routes at `/v1/audit/objects/{id}` and `/v1/audit/timeline`.
```

- [ ] **Step 3: Commit**

```bash
git add STATUS.md TODO.md
git commit -m "docs: update STATUS.md and TODO.md for audit service"
```
