"""DB job tracker for ingest CLI passes (PLAN P1-7).

Mirrors filesystem-driven pass completions into the IngestJob /
IngestJobPass tables so multiple contributors and reviewers can see
the live state of an ingestion run without each having a local copy
of the project directory.

Designed to be opt-in and best-effort: if no `job_id` is set on the
project manifest, every method is a no-op; if the DB is unreachable,
errors are swallowed with a console warning rather than failing the
ingestion.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from capability_commons.services.ingest import IngestService

if TYPE_CHECKING:
    from capability_commons.cli.ingest.project import IngestProject


class JobTracker:
    """Thin async wrapper around IngestService scoped to one job_id.

    A `None` `job_id` makes every method a no-op so call sites can wrap
    pass execution unconditionally without branching.
    """

    def __init__(self, db_url: str | None, job_id: uuid.UUID | None) -> None:
        self.db_url = db_url
        self.job_id = job_id

    @property
    def enabled(self) -> bool:
        return self.job_id is not None and self.db_url is not None

    @asynccontextmanager
    async def _session(self):
        if not self.enabled:
            yield None
            return
        engine = create_async_engine(self.db_url)
        factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        try:
            async with factory() as session:
                yield session
                await session.commit()
        finally:
            await engine.dispose()

    async def start(self, pass_name: str) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as session:
                if session is None:
                    return
                await IngestService(session).start_pass(self.job_id, pass_name)
        except Exception as exc:  # noqa: BLE001 — best-effort tracker
            _warn(f"start_pass({pass_name}) failed: {exc}")

    async def complete(
        self,
        pass_name: str,
        *,
        output_path: str | None = None,
        artifact_count: int = 0,
    ) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as session:
                if session is None:
                    return
                await IngestService(session).complete_pass(
                    self.job_id,
                    pass_name,
                    output_path=output_path,
                    artifact_count=artifact_count,
                )
        except Exception as exc:  # noqa: BLE001
            _warn(f"complete_pass({pass_name}) failed: {exc}")

    async def fail(self, pass_name: str, error_message: str) -> None:
        if not self.enabled:
            return
        try:
            async with self._session() as session:
                if session is None:
                    return
                await IngestService(session).fail_pass(
                    self.job_id, pass_name, error_message
                )
        except Exception as exc:  # noqa: BLE001
            _warn(f"fail_pass({pass_name}) failed: {exc}")


def tracker_for(project: "IngestProject", db_url: str | None = None) -> JobTracker:
    """Build a JobTracker from a project's manifest. Returns a disabled
    tracker (no-op) if the manifest has no job_id."""
    raw = project.manifest.job_id
    job_uuid: uuid.UUID | None = None
    if raw:
        try:
            job_uuid = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            _warn(f"manifest job_id is not a valid UUID: {raw!r}")
    return JobTracker(db_url=db_url, job_id=job_uuid)


def _warn(message: str) -> None:
    try:
        from rich.console import Console
        Console().print(f"[yellow]job tracker:[/yellow] {message}")
    except Exception:  # noqa: BLE001
        print(f"job tracker: {message}")
