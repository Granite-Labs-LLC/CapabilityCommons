"""Unit tests for the ingest JobTracker (PLAN P1-7).

The tracker is best-effort and DB-backed; these tests validate behavior
without a live Postgres by exercising the no-op path and the bind logic.
"""
from __future__ import annotations

import asyncio
import uuid

from capability_commons.cli.ingest.job_tracker import JobTracker, tracker_for
from capability_commons.cli.ingest.project import IngestProject


def _project(tmp_path):
    return IngestProject.init(
        projects_root=tmp_path / "projects",
        name="test-tracker",
        sources=[{"id": "src.x", "file": "sources/x.pdf",
                   "title": "X", "source_kind": "BOOK"}],
    )


def test_tracker_disabled_when_no_job_id(tmp_path):
    project = _project(tmp_path)
    tracker = tracker_for(project, db_url="postgresql+asyncpg://nope")
    assert tracker.enabled is False


def test_tracker_disabled_when_no_db_url(tmp_path):
    project = _project(tmp_path)
    project.bind_job(str(uuid.uuid4()))
    tracker = tracker_for(project, db_url=None)
    assert tracker.enabled is False


def test_tracker_enabled_with_job_and_url(tmp_path):
    project = _project(tmp_path)
    project.bind_job(str(uuid.uuid4()))
    tracker = tracker_for(project, db_url="postgresql+asyncpg://x/y")
    assert tracker.enabled is True


def test_disabled_tracker_methods_are_no_ops():
    """All async methods on a disabled tracker must complete without I/O."""
    tracker = JobTracker(db_url=None, job_id=None)
    asyncio.run(tracker.start("parse"))
    asyncio.run(tracker.complete("parse"))
    asyncio.run(tracker.fail("parse", "boom"))


def test_invalid_job_uuid_disables_tracker(tmp_path):
    project = _project(tmp_path)
    project.bind_job("not-a-uuid")
    tracker = tracker_for(project, db_url="postgresql+asyncpg://x/y")
    assert tracker.enabled is False


def test_bind_job_persists_to_manifest(tmp_path):
    project = _project(tmp_path)
    job_uuid = str(uuid.uuid4())
    project.bind_job(job_uuid)
    # Reload from disk and confirm the manifest carries the binding.
    reloaded = IngestProject.load(tmp_path / "projects", "test-tracker")
    assert reloaded.manifest.job_id == job_uuid


def test_mark_pass_complete_does_not_raise_when_db_unreachable(tmp_path):
    """The DB mirror is best-effort; an unreachable DB must not break the
    filesystem-driven pipeline."""
    project = _project(tmp_path)
    project.bind_job(str(uuid.uuid4()))
    # No DB is running on this URL; mark_pass_complete should swallow the
    # connection error and still update the manifest.
    project.mark_pass_complete("parse")
    assert project.manifest.passes.parse.completed is not None
