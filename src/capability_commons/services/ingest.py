"""Ingest job service — DB-backed tracking for the 8-pass ingestion pipeline.

Provides create/get/list for jobs and start/complete/fail for individual passes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
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
