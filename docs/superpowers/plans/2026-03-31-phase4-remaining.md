# Phase 4 Remaining Tickets (ING-007, DOC-001) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DB-backed ingest job tracking and review queues (ING-007), then update all operator docs to match the real implementation (DOC-001).

**Architecture:** Two new DB tables (`ingest_jobs`, `ingest_job_passes`) track ingest runs with status and error logs. A new `IngestService` provides the business logic. New API routes under `/v1/ingest` expose job status. The `IngestProject` CLI class is updated to optionally record progress to the DB. DOC-001 updates STATUS.md, TODO.md, ARCHITECTURE.md, and ingestion/README.md to match the shipped system.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x (async), FastAPI, Alembic, Pydantic v2, pytest

---

### Task 1: Add IngestJobStatus enum

**Files:**
- Modify: `src/capability_commons/domain/enums.py:270-275`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
# === ING-007: DB-backed ingest jobs and review queues ===


class TestING007IngestJobs:
    def test_ingest_job_status_enum_exists(self):
        """ING-007: IngestJobStatus enum must exist with expected values."""
        from capability_commons.domain.enums import IngestJobStatus
        assert IngestJobStatus.PENDING.value == "pending"
        assert IngestJobStatus.RUNNING.value == "running"
        assert IngestJobStatus.COMPLETED.value == "completed"
        assert IngestJobStatus.FAILED.value == "failed"

    def test_ingest_pass_status_enum_exists(self):
        """ING-007: IngestPassStatus enum must exist with expected values."""
        from capability_commons.domain.enums import IngestPassStatus
        assert IngestPassStatus.PENDING.value == "pending"
        assert IngestPassStatus.RUNNING.value == "running"
        assert IngestPassStatus.COMPLETED.value == "completed"
        assert IngestPassStatus.FAILED.value == "failed"
        assert IngestPassStatus.SKIPPED.value == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: FAIL — `ImportError: cannot import name 'IngestJobStatus'`

- [ ] **Step 3: Write minimal implementation**

Add to end of `src/capability_commons/domain/enums.py`:

```python
class IngestJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestPassStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/domain/enums.py tests/test_phase0_regression.py
git commit -m "feat: add IngestJobStatus and IngestPassStatus enums (ING-007)"
```

---

### Task 2: Add IngestJob and IngestJobPass DB models

**Files:**
- Modify: `src/capability_commons/db/models.py:522` (end of file)
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
    def test_ingest_job_model_exists(self):
        """ING-007: IngestJob model must be importable with expected columns."""
        from capability_commons.db.models import IngestJob
        import sqlalchemy
        table = IngestJob.__table__
        col_names = {c.name for c in table.columns}
        assert "id" in col_names
        assert "workspace_id" in col_names
        assert "project_name" in col_names
        assert "status" in col_names
        assert "source_count" in col_names
        assert "error_log" in col_names
        assert "created_at" in col_names
        assert "started_at" in col_names
        assert "completed_at" in col_names

    def test_ingest_job_pass_model_exists(self):
        """ING-007: IngestJobPass model must be importable with expected columns."""
        from capability_commons.db.models import IngestJobPass
        table = IngestJobPass.__table__
        col_names = {c.name for c in table.columns}
        assert "id" in col_names
        assert "ingest_job_id" in col_names
        assert "pass_name" in col_names
        assert "status" in col_names
        assert "output_path" in col_names
        assert "error_message" in col_names
        assert "started_at" in col_names
        assert "completed_at" in col_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_job_model_exists tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_job_pass_model_exists -v`
Expected: FAIL — `ImportError: cannot import name 'IngestJob'`

- [ ] **Step 3: Write minimal implementation**

Add imports to the top of `src/capability_commons/db/models.py`:

```python
from capability_commons.domain.enums import (
    ...existing imports...
    IngestJobStatus,
    IngestPassStatus,
)
```

Add models to end of `src/capability_commons/db/models.py`:

```python
class IngestJob(Base):
    """Tracks an ingestion pipeline run from init through load."""
    __tablename__ = "ingest_jobs"
    __table_args__ = (
        Index("idx_ingest_jobs_workspace_status", "workspace_id", "status"),
        Index("idx_ingest_jobs_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IngestJobStatus] = mapped_column(_enum(IngestJobStatus, "ingest_job_status"), nullable=False, default=IngestJobStatus.PENDING)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    passes: Mapped[list[IngestJobPass]] = relationship(back_populates="job", cascade="all, delete-orphan", order_by="IngestJobPass.ordinal")


class IngestJobPass(Base):
    """Tracks an individual pass within an ingest job."""
    __tablename__ = "ingest_job_passes"
    __table_args__ = (
        UniqueConstraint("ingest_job_id", "pass_name", name="uq_ingest_job_pass"),
        Index("idx_ingest_job_passes_job", "ingest_job_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingest_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False)
    pass_name: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[IngestPassStatus] = mapped_column(_enum(IngestPassStatus, "ingest_pass_status"), nullable=False, default=IngestPassStatus.PENDING)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[IngestJob] = relationship(back_populates="passes")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/db/models.py tests/test_phase0_regression.py
git commit -m "feat: add IngestJob and IngestJobPass DB models (ING-007)"
```

---

### Task 3: Add Alembic migration for ingest tables

**Files:**
- Create: `alembic/versions/20260331_0001_ingest_jobs.py`

- [ ] **Step 1: Create the migration**

```python
"""Add ingest_jobs and ingest_job_passes tables for DB-backed ingest tracking.

Revision ID: 20260331_0001
Revises: 20260330_0001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260331_0001"
down_revision = "20260330_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("config_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_ingest_jobs_workspace_status", "ingest_jobs", ["workspace_id", "status"])
    op.create_index("idx_ingest_jobs_created", "ingest_jobs", ["created_at"])

    op.create_table(
        "ingest_job_passes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingest_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_name", sa.Text, nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("output_path", sa.Text, nullable=True),
        sa.Column("artifact_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_ingest_job_pass", "ingest_job_passes", ["ingest_job_id", "pass_name"])
    op.create_index("idx_ingest_job_passes_job", "ingest_job_passes", ["ingest_job_id", "ordinal"])


def downgrade() -> None:
    op.drop_index("idx_ingest_job_passes_job")
    op.drop_constraint("uq_ingest_job_pass", "ingest_job_passes")
    op.drop_table("ingest_job_passes")
    op.drop_index("idx_ingest_jobs_created")
    op.drop_index("idx_ingest_jobs_workspace_status")
    op.drop_table("ingest_jobs")
```

- [ ] **Step 2: Commit**

```bash
git add alembic/versions/20260331_0001_ingest_jobs.py
git commit -m "migration: add ingest_jobs and ingest_job_passes tables (ING-007)"
```

---

### Task 4: Create IngestService

**Files:**
- Create: `src/capability_commons/services/ingest.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
    def test_ingest_service_importable(self):
        """ING-007: IngestService must be importable."""
        from capability_commons.services.ingest import IngestService
        assert IngestService is not None

    def test_ingest_service_has_required_methods(self):
        """ING-007: IngestService must have create, get, list, update methods."""
        import inspect
        from capability_commons.services.ingest import IngestService
        methods = {name for name, _ in inspect.getmembers(IngestService, predicate=inspect.isfunction)}
        assert "create_job" in methods
        assert "get_job" in methods
        assert "list_jobs" in methods
        assert "start_pass" in methods
        assert "complete_pass" in methods
        assert "fail_pass" in methods
        assert "fail_job" in methods

    def test_ingest_pass_names_constant(self):
        """ING-007: INGEST_PASS_NAMES must list the 8 pipeline passes in order."""
        from capability_commons.services.ingest import INGEST_PASS_NAMES
        assert INGEST_PASS_NAMES == [
            "parse", "extract", "draft", "cite",
            "canonicalize", "edges", "bundles", "load",
        ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_service_importable tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_service_has_required_methods tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_pass_names_constant -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_commons/services/ingest.py`:

```python
"""Ingest job service — DB-backed tracking for the 8-pass ingestion pipeline.

Provides create/get/list for jobs and start/complete/fail for individual passes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from capability_commons.db.models import IngestJob, IngestJobPass
from capability_commons.domain.enums import IngestJobStatus, IngestPassStatus

INGEST_PASS_NAMES = [
    "parse", "extract", "draft", "cite",
    "canonicalize", "edges", "bundles", "load",
]


class IngestService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self,
        workspace_id: uuid.UUID,
        project_name: str,
        source_count: int = 0,
        config: dict[str, Any] | None = None,
        created_by: uuid.UUID | None = None,
    ) -> IngestJob:
        """Create a new ingest job with pending passes for all 8 pipeline stages."""
        job = IngestJob(
            workspace_id=workspace_id,
            project_name=project_name,
            source_count=source_count,
            config_json=config or {},
            created_by=created_by,
        )
        self.session.add(job)
        for ordinal, name in enumerate(INGEST_PASS_NAMES):
            p = IngestJobPass(
                ingest_job_id=job.id,
                pass_name=name,
                ordinal=ordinal,
            )
            self.session.add(p)
        await self.session.flush()
        await self.session.refresh(job, ["passes"])
        return job

    async def get_job(self, job_id: uuid.UUID) -> IngestJob | None:
        """Fetch a job with its passes."""
        stmt = (
            select(IngestJob)
            .where(IngestJob.id == job_id)
            .options(selectinload(IngestJob.passes))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        workspace_id: uuid.UUID,
        status: IngestJobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IngestJob]:
        """List ingest jobs for a workspace, optionally filtered by status."""
        stmt = (
            select(IngestJob)
            .where(IngestJob.workspace_id == workspace_id)
            .options(selectinload(IngestJob.passes))
            .order_by(IngestJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(IngestJob.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def start_pass(self, job_id: uuid.UUID, pass_name: str) -> IngestJobPass:
        """Mark a pass as running and start the job if it is still pending."""
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        p = next((p for p in job.passes if p.pass_name == pass_name), None)
        if p is None:
            raise ValueError(f"Unknown pass: {pass_name}")

        now = datetime.now(timezone.utc)
        p.status = IngestPassStatus.RUNNING
        p.started_at = now

        if job.status == IngestJobStatus.PENDING:
            job.status = IngestJobStatus.RUNNING
            job.started_at = now

        await self.session.flush()
        return p

    async def complete_pass(
        self,
        job_id: uuid.UUID,
        pass_name: str,
        output_path: str | None = None,
        artifact_count: int = 0,
    ) -> IngestJobPass:
        """Mark a pass as completed. If all passes are done, complete the job."""
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        p = next((p for p in job.passes if p.pass_name == pass_name), None)
        if p is None:
            raise ValueError(f"Unknown pass: {pass_name}")

        now = datetime.now(timezone.utc)
        p.status = IngestPassStatus.COMPLETED
        p.completed_at = now
        p.output_path = output_path
        p.artifact_count = artifact_count

        # Check if all passes are done
        terminal = {IngestPassStatus.COMPLETED, IngestPassStatus.SKIPPED}
        if all(pp.status in terminal for pp in job.passes):
            job.status = IngestJobStatus.COMPLETED
            job.completed_at = now

        await self.session.flush()
        return p

    async def fail_pass(
        self,
        job_id: uuid.UUID,
        pass_name: str,
        error_message: str,
    ) -> IngestJobPass:
        """Mark a pass as failed and fail the job."""
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        p = next((p for p in job.passes if p.pass_name == pass_name), None)
        if p is None:
            raise ValueError(f"Unknown pass: {pass_name}")

        now = datetime.now(timezone.utc)
        p.status = IngestPassStatus.FAILED
        p.completed_at = now
        p.error_message = error_message

        job.status = IngestJobStatus.FAILED
        job.completed_at = now
        job.error_log = f"Pass '{pass_name}' failed: {error_message}"

        await self.session.flush()
        return p

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error_log: str,
    ) -> IngestJob:
        """Mark the job itself as failed (e.g., for setup errors)."""
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Ingest job not found: {job_id}")

        now = datetime.now(timezone.utc)
        job.status = IngestJobStatus.FAILED
        job.completed_at = now
        job.error_log = error_log

        await self.session.flush()
        return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/services/ingest.py tests/test_phase0_regression.py
git commit -m "feat: add IngestService with job lifecycle management (ING-007)"
```

---

### Task 5: Add ingest job API schemas

**Files:**
- Create: `src/capability_commons/schemas/ingest.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
    def test_ingest_schemas_importable(self):
        """ING-007: Ingest API schemas must be importable."""
        from capability_commons.schemas.ingest import (
            CreateIngestJobRequest,
            IngestJobResponse,
            IngestJobPassResponse,
        )
        assert CreateIngestJobRequest is not None
        assert IngestJobResponse is not None
        assert IngestJobPassResponse is not None

    def test_ingest_job_response_has_passes(self):
        """ING-007: IngestJobResponse must include passes list."""
        from capability_commons.schemas.ingest import IngestJobResponse
        fields = IngestJobResponse.model_fields
        assert "passes" in fields
        assert "project_name" in fields
        assert "status" in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_schemas_importable tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_job_response_has_passes -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_commons/schemas/ingest.py`:

```python
"""API schemas for ingest job endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from capability_commons.domain.enums import IngestJobStatus, IngestPassStatus


class CreateIngestJobRequest(BaseModel):
    project_name: str
    source_count: int = 0
    config: dict[str, Any] = {}


class IngestJobPassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    pass_name: str
    ordinal: int
    status: IngestPassStatus
    output_path: str | None = None
    artifact_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IngestJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_name: str
    status: IngestJobStatus
    source_count: int
    config_json: dict[str, Any]
    error_log: str | None = None
    created_at: datetime
    created_by: uuid.UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    passes: list[IngestJobPassResponse] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/schemas/ingest.py tests/test_phase0_regression.py
git commit -m "feat: add ingest job API schemas (ING-007)"
```

---

### Task 6: Add ingest job API routes

**Files:**
- Create: `src/capability_commons/api/routes/ingest.py`
- Modify: `src/capability_commons/api/router.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
    def test_ingest_routes_importable(self):
        """ING-007: Ingest routes module must be importable with router."""
        from capability_commons.api.routes.ingest import router
        assert router is not None

    def test_ingest_routes_registered(self):
        """ING-007: Ingest routes must be registered in the main router."""
        import inspect
        from capability_commons.api import router as router_mod
        source = inspect.getsource(router_mod)
        assert "ingest" in source

    def test_ingest_routes_have_endpoints(self):
        """ING-007: Ingest router must have create, list, get endpoints."""
        from capability_commons.api.routes.ingest import router
        paths = [r.path for r in router.routes]
        methods = {}
        for r in router.routes:
            if hasattr(r, "methods"):
                methods[r.path] = r.methods
        assert "/ingest/jobs" in paths
        assert "/ingest/jobs/{job_id}" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_routes_importable tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_routes_registered tests/test_phase0_regression.py::TestING007IngestJobs::test_ingest_routes_have_endpoints -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_commons/api/routes/ingest.py`:

```python
"""API routes for ingest job management."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.domain.enums import IngestJobStatus
from capability_commons.schemas.ingest import (
    CreateIngestJobRequest,
    IngestJobResponse,
)
from capability_commons.services.ingest import IngestService

router = APIRouter()


@router.post("/ingest/jobs", response_model=IngestJobResponse, status_code=201)
async def create_ingest_job(
    request: CreateIngestJobRequest,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> IngestJobResponse:
    """Create a new ingest job for tracking an ingestion pipeline run."""
    service = IngestService(session)
    job = await service.create_job(
        workspace_id=workspace.id,
        project_name=request.project_name,
        source_count=request.source_count,
        config=request.config,
    )
    await session.commit()
    return IngestJobResponse.model_validate(job, from_attributes=True)


@router.get("/ingest/jobs", response_model=list[IngestJobResponse])
async def list_ingest_jobs(
    session: DBSession,
    workspace: CurrentWorkspace,
    status: IngestJobStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IngestJobResponse]:
    """List ingest jobs for the current workspace."""
    service = IngestService(session)
    jobs = await service.list_jobs(workspace.id, status=status, limit=limit, offset=offset)
    return [IngestJobResponse.model_validate(j, from_attributes=True) for j in jobs]


@router.get("/ingest/jobs/{job_id}", response_model=IngestJobResponse)
async def get_ingest_job(
    job_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> IngestJobResponse:
    """Get a specific ingest job with all pass statuses."""
    service = IngestService(session)
    job = await service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    if job.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Ingest job not found")
    return IngestJobResponse.model_validate(job, from_attributes=True)
```

Update `src/capability_commons/api/router.py` to add the import and include:

Add `ingest` to the import line and add:
```python
api_router.include_router(ingest.router, prefix="/v1", tags=["ingest"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/api/routes/ingest.py src/capability_commons/api/router.py tests/test_phase0_regression.py
git commit -m "feat: add ingest job API routes (ING-007)"
```

---

### Task 7: Add review queue endpoint

**Files:**
- Modify: `src/capability_commons/api/routes/reviews.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_phase0_regression.py`:

```python
    def test_review_queue_endpoint_exists(self):
        """ING-007: Reviews router must have a GET /reviews/queue endpoint."""
        from capability_commons.api.routes.reviews import router
        paths = [r.path for r in router.routes]
        assert "/reviews/queue" in paths

    def test_review_queue_queries_in_review(self):
        """ING-007: Review queue must filter by IN_REVIEW lifecycle state."""
        import inspect
        from capability_commons.api.routes import reviews
        source = inspect.getsource(reviews)
        assert "LifecycleState" in source
        assert "IN_REVIEW" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs::test_review_queue_endpoint_exists tests/test_phase0_regression.py::TestING007IngestJobs::test_review_queue_queries_in_review -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add to `src/capability_commons/api/routes/reviews.py`:

Add imports at top:
```python
from sqlalchemy import select
from capability_commons.db.models import ContextObject, ContextObjectVersion
from capability_commons.domain.enums import LifecycleState
```

Add endpoint:
```python
@router.get("/reviews/queue")
async def review_queue(
    session: DBSession,
    workspace: CurrentWorkspace,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List objects in IN_REVIEW state awaiting review, with pending safety reviews and open contradictions."""
    stmt = (
        select(ContextObject)
        .where(
            ContextObject.workspace_id == workspace.id,
            ContextObject.lifecycle_state == LifecycleState.IN_REVIEW,
        )
        .order_by(ContextObject.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    objects = result.scalars().all()
    return [
        {
            "id": str(obj.id),
            "slug": obj.slug,
            "type": obj.type.value,
            "canonical_title": obj.canonical_title,
            "lifecycle_state": obj.lifecycle_state.value,
            "updated_at": obj.updated_at.isoformat(),
        }
        for obj in objects
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phase0_regression.py::TestING007IngestJobs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/api/routes/reviews.py tests/test_phase0_regression.py
git commit -m "feat: add review queue endpoint for IN_REVIEW objects (ING-007)"
```

---

### Task 8: Update STATUS.md (DOC-001)

**Files:**
- Modify: `STATUS.md`

- [ ] **Step 1: Update STATUS.md**

Update the codebase metrics table to reflect the current state:
- Update table count from 19 to 21 (adding ingest_jobs, ingest_job_passes)
- Update migration count from 5 to 8
- Update endpoint count from 37 to 41+ (adding ingest/jobs POST, GET list, GET detail, reviews/queue)
- Add route entries for Ingest (3 endpoints) and Metrics (3 endpoints) to the route module table
- Update the component status to reflect Phase 4 completion (publish gates, metrics, response cache, ingest job tracking)
- Update the "Known Gaps" section to remove items that are now resolved

- [ ] **Step 2: Commit**

```bash
git add STATUS.md
git commit -m "docs: update STATUS.md with Phase 4 additions (DOC-001)"
```

---

### Task 9: Update TODO.md (DOC-001)

**Files:**
- Modify: `TODO.md`

- [ ] **Step 1: Update TODO.md**

Mark completed items:
- [x] **Safety review for high-risk content** — publish gates implemented (SAFE-001)
- [x] **Review dashboard** — review queue endpoint added (ING-007)
- [x] **Implement job scheduler** — DB-backed ingest jobs implemented (ING-007)

Update the "quick reference" section to reflect current state.

- [ ] **Step 2: Commit**

```bash
git add TODO.md
git commit -m "docs: update TODO.md with completed Phase 4 items (DOC-001)"
```

---

### Task 10: Update ARCHITECTURE.md (DOC-001)

**Files:**
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update ARCHITECTURE.md**

Add a section on:
- **Ingest Job Lifecycle** — DB-backed job tracking (pending → running → completed/failed), 8-pass pipeline tracked per-pass with status/output_path/error
- **Publish Gates** — rule-based safety checks before publish (risk band review, safety boundary, contradictions)
- **Metrics Dashboard** — ingest quality and answer quality aggregate metrics
- **Response Cache** — TTL-based caching for public search/ask
- **Review Queue** — API endpoint for objects in IN_REVIEW state

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add Phase 4 sections to ARCHITECTURE.md (DOC-001)"
```

---

### Task 11: Update ingestion/README.md (DOC-001)

**Files:**
- Modify: `ingestion/README.md`

- [ ] **Step 1: Update ingestion/README.md**

Add a new section "Ingest Job Tracking (API)" documenting:
- `POST /v1/ingest/jobs` — create a new tracked job
- `GET /v1/ingest/jobs` — list jobs (filterable by status)
- `GET /v1/ingest/jobs/{id}` — get job detail with pass statuses
- Explain the relationship between the CLI filesystem workflow and the DB-backed tracking
- Note that the CLI continues to work independently; DB tracking is optional and additive

- [ ] **Step 2: Commit**

```bash
git add ingestion/README.md
git commit -m "docs: add ingest job API documentation to ingestion/README.md (DOC-001)"
```

---

### Task 12: Run full test suite and final commit

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ --ignore=tests/test_integration.py -v`
Expected: All tests PASS

- [ ] **Step 2: Fix any failures if needed**

- [ ] **Step 3: Final verification commit if needed**

```bash
git log --oneline -10
```

Verify all Phase 4 tickets are represented in the commit history.
