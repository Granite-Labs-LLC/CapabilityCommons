# Storage Adapter + File Routes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable file attachments (diagrams, photos, worksheets) on knowledge object versions via a storage adapter with local filesystem implementation and REST API routes.

**Architecture:** Abstract `StorageAdapter` with `LocalStorageAdapter` implementation, configuration via pydantic-settings, Alembic migration for the `object_files` table (model already exists), API routes for upload/download/list/delete, and dependency injection.

**Tech Stack:** SQLAlchemy 2 async, Alembic, FastAPI (UploadFile, StreamingResponse), Pydantic v2, pytest, hashlib

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/capability_commons/config.py` | Add storage settings |
| `src/capability_commons/storage/adapters.py` | `StorageAdapter` ABC + `LocalStorageAdapter` + `S3StorageAdapter` stub |
| `alembic/versions/20260402_0002_object_files.py` | Migration for object_files table |
| `src/capability_commons/schemas/files.py` | `FileMetadataResponse` schema |
| `src/capability_commons/api/routes/files.py` | Upload, list, download, delete routes |
| `src/capability_commons/api/router.py` | Wire file routes |
| `tests/test_storage.py` | Unit tests for adapter, schemas, routes |
| `tests/test_integration_storage.py` | Integration tests with real DB + filesystem |

---

### Task 1: Add Storage Configuration

**Files:**
- Modify: `src/capability_commons/config.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_storage.py`:

```python
"""Tests for the storage adapter and file routes."""
from __future__ import annotations


def test_storage_settings_exist():
    """Config should have storage settings."""
    from capability_commons.config import Settings

    fields = Settings.model_fields
    assert "storage_backend" in fields
    assert "storage_root" in fields
    assert "storage_max_file_size" in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_storage_settings_exist -v`
Expected: FAIL

- [ ] **Step 3: Add settings to config.py**

Add to `src/capability_commons/config.py` in the `Settings` class (after the Worker section):

```python
    # Storage
    storage_backend: str = "local"
    storage_root: str = "./data/files"
    storage_max_file_size: int = 52428800  # 50MB
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_storage_settings_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/config.py tests/test_storage.py
git commit -m "feat(storage): add storage configuration settings"
```

---

### Task 2: Implement Storage Adapters

**Files:**
- Create: `src/capability_commons/storage/adapters.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_storage.py`:

```python
import os
import tempfile


def test_storage_adapter_abc():
    """StorageAdapter should define put, get, delete, exists."""
    from capability_commons.storage.adapters import StorageAdapter
    import abc

    assert abc.ABC in StorageAdapter.__mro__
    for method in ("put", "get", "delete", "exists"):
        assert hasattr(StorageAdapter, method)


def test_local_storage_put_get_delete():
    """LocalStorageAdapter should store, retrieve, and delete files."""
    from capability_commons.storage.adapters import LocalStorageAdapter

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = LocalStorageAdapter(root=tmpdir)

        key = "abc123testkey"
        data = b"Hello, storage!"
        adapter.put(key, data, "text/plain")

        assert adapter.exists(key)

        retrieved = adapter.get(key)
        assert retrieved == data

        adapter.delete(key)
        assert not adapter.exists(key)


def test_local_storage_get_missing_raises():
    """get() on a missing key should raise FileNotFoundError."""
    from capability_commons.storage.adapters import LocalStorageAdapter
    import pytest

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = LocalStorageAdapter(root=tmpdir)
        with pytest.raises(FileNotFoundError):
            adapter.get("nonexistent")


def test_s3_adapter_raises_not_implemented():
    """S3StorageAdapter methods should raise NotImplementedError."""
    from capability_commons.storage.adapters import S3StorageAdapter
    import pytest

    adapter = S3StorageAdapter()
    with pytest.raises(NotImplementedError):
        adapter.put("key", b"data", "text/plain")
    with pytest.raises(NotImplementedError):
        adapter.get("key")
    with pytest.raises(NotImplementedError):
        adapter.delete("key")
    with pytest.raises(NotImplementedError):
        adapter.exists("key")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_storage.py -v`
Expected: 4 new tests FAIL

- [ ] **Step 3: Implement the adapters**

Create `src/capability_commons/storage/adapters.py`:

```python
"""Storage adapters for file attachments."""
from __future__ import annotations

import abc
import os
from pathlib import Path


class StorageAdapter(abc.ABC):
    """Abstract base for file storage backends."""

    @abc.abstractmethod
    def put(self, key: str, data: bytes, media_type: str) -> None:
        """Store a file."""

    @abc.abstractmethod
    def get(self, key: str) -> bytes:
        """Retrieve a file. Raises FileNotFoundError if missing."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Delete a file. Raises FileNotFoundError if missing."""

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a file exists."""


class LocalStorageAdapter(StorageAdapter):
    """Store files on the local filesystem with two-level hash prefix directories."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path_for(self, key: str) -> Path:
        return self.root / key[:2] / key[2:4] / key

    def put(self, key: str, data: bytes, media_type: str) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        path.unlink()

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()


class S3StorageAdapter(StorageAdapter):
    """Stub for future S3-compatible storage. Not yet implemented."""

    def put(self, key: str, data: bytes, media_type: str) -> None:
        raise NotImplementedError("S3 adapter not yet implemented")

    def get(self, key: str) -> bytes:
        raise NotImplementedError("S3 adapter not yet implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("S3 adapter not yet implemented")

    def exists(self, key: str) -> bool:
        raise NotImplementedError("S3 adapter not yet implemented")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_storage.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/storage/adapters.py tests/test_storage.py
git commit -m "feat(storage): implement StorageAdapter ABC and LocalStorageAdapter"
```

---

### Task 3: Create object_files Migration

**Files:**
- Create: `alembic/versions/20260402_0002_object_files.py`

- [ ] **Step 1: Create the migration**

Create `alembic/versions/20260402_0002_object_files.py`:

```python
"""Add object_files table.

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "object_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("context_object_version_id", UUID(as_uuid=True), sa.ForeignKey("context_object_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_store_key", sa.Text, nullable=False),
        sa.Column("media_type", sa.Text, nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=True),
        sa.Column("checksum", sa.Text, nullable=True),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="byte_size_non_negative"),
    )
    op.create_index("idx_object_files_version", "object_files", ["context_object_version_id"])


def downgrade() -> None:
    op.drop_index("idx_object_files_version", table_name="object_files")
    op.drop_table("object_files")
```

- [ ] **Step 2: Commit**

```bash
git add alembic/versions/20260402_0002_object_files.py
git commit -m "feat(storage): add object_files table migration"
```

---

### Task 4: Add File Schemas

**Files:**
- Create: `src/capability_commons/schemas/files.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_storage.py`:

```python
def test_file_metadata_schema():
    """FileMetadataResponse should have expected fields."""
    from capability_commons.schemas.files import FileMetadataResponse

    fields = FileMetadataResponse.model_fields
    expected = {"id", "object_store_key", "media_type", "byte_size", "checksum", "label", "created_at"}
    assert expected.issubset(set(fields.keys())), f"Missing: {expected - set(fields.keys())}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_file_metadata_schema -v`
Expected: FAIL

- [ ] **Step 3: Create the schema**

Create `src/capability_commons/schemas/files.py`:

```python
"""Schemas for file attachment API responses."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FileMetadataResponse(BaseModel):
    id: uuid.UUID
    object_store_key: str
    media_type: str
    byte_size: int | None = None
    checksum: str | None = None
    label: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py::test_file_metadata_schema -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/schemas/files.py tests/test_storage.py
git commit -m "feat(storage): add FileMetadataResponse schema"
```

---

### Task 5: Add File API Routes

**Files:**
- Create: `src/capability_commons/api/routes/files.py`
- Modify: `src/capability_commons/api/router.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_storage.py`:

```python
def test_file_routes_wired():
    """File routes should be wired and return 401 (not 404) without auth."""
    import uuid
    from fastapi.testclient import TestClient
    from capability_commons.main import app

    client = TestClient(app)
    oid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    fid = str(uuid.uuid4())

    # POST upload should require auth
    r = client.post(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    # GET list should require auth
    r = client.get(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    # GET download should require auth
    r = client.get(f"/v1/objects/{oid}/versions/{vid}/files/{fid}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    # DELETE should require auth
    r = client.delete(f"/v1/objects/{oid}/versions/{vid}/files/{fid}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py::test_file_routes_wired -v`
Expected: FAIL (404s, not 401s — routes don't exist yet)

- [ ] **Step 3: Create the route module**

Create `src/capability_commons/api/routes/files.py`:

```python
"""File attachment API routes."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from capability_commons.api.deps import CurrentWorkspace, DBSession
from capability_commons.config import get_settings
from capability_commons.db.models import ObjectFile
from capability_commons.schemas.files import FileMetadataResponse
from capability_commons.storage.adapters import LocalStorageAdapter, StorageAdapter

router = APIRouter()

ALLOWED_MEDIA_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "application/pdf", "text/plain", "text/markdown", "text/csv",
}


def get_storage_adapter() -> StorageAdapter:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorageAdapter(root=settings.storage_root)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


@router.post(
    "/objects/{object_id}/versions/{version_id}/files",
    response_model=FileMetadataResponse,
    status_code=201,
)
async def upload_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file: UploadFile,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
    label: str | None = None,
):
    settings = get_settings()

    media_type = file.content_type or "application/octet-stream"
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(415, f"Media type not allowed: {media_type}. Allowed: {sorted(ALLOWED_MEDIA_TYPES)}")

    data = await file.read()
    if len(data) > settings.storage_max_file_size:
        raise HTTPException(413, f"File too large. Maximum size: {settings.storage_max_file_size} bytes")

    checksum = hashlib.sha256(data).hexdigest()
    key = uuid.uuid4().hex

    storage.put(key, data, media_type)

    obj_file = ObjectFile(
        context_object_version_id=version_id,
        object_store_key=key,
        media_type=media_type,
        byte_size=len(data),
        checksum=checksum,
        label=label,
    )
    session.add(obj_file)
    await session.flush()
    await session.commit()
    await session.refresh(obj_file)
    return obj_file


@router.get(
    "/objects/{object_id}/versions/{version_id}/files",
    response_model=list[FileMetadataResponse],
)
async def list_files(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
):
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.context_object_version_id == version_id)
    )
    return list(result.scalars().all())


@router.get("/objects/{object_id}/versions/{version_id}/files/{file_id}")
async def download_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
):
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.id == file_id)
    )
    obj_file = result.scalar_one_or_none()
    if not obj_file:
        raise HTTPException(404, "File not found")

    try:
        data = storage.get(obj_file.object_store_key)
    except FileNotFoundError:
        raise HTTPException(404, "File data not found in storage")

    return Response(content=data, media_type=obj_file.media_type)


@router.delete(
    "/objects/{object_id}/versions/{version_id}/files/{file_id}",
    status_code=204,
)
async def delete_file(
    object_id: uuid.UUID,
    version_id: uuid.UUID,
    file_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
    storage: StorageAdapter = Depends(get_storage_adapter),
):
    result = await session.execute(
        select(ObjectFile).where(ObjectFile.id == file_id)
    )
    obj_file = result.scalar_one_or_none()
    if not obj_file:
        raise HTTPException(404, "File not found")

    try:
        storage.delete(obj_file.object_store_key)
    except FileNotFoundError:
        pass  # File already gone from storage — still delete DB record

    await session.delete(obj_file)
    await session.commit()
```

- [ ] **Step 4: Wire the routes in router.py**

Add to `src/capability_commons/api/router.py`:

Import: add `files` to the imports from `capability_commons.api.routes`

Add line:
```python
api_router.include_router(files.router, prefix="/v1", tags=["files"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/api/routes/files.py src/capability_commons/api/router.py tests/test_storage.py
git commit -m "feat(storage): add file upload/download/list/delete routes"
```

---

### Task 6: Integration Tests for Storage

**Files:**
- Create: `tests/test_integration_storage.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the integration test file**

Create `tests/test_integration_storage.py`:

```python
"""Integration tests for file storage: upload, list, download, delete via real DB."""
from __future__ import annotations

import tempfile
import uuid

import pytest
from sqlalchemy import select

from capability_commons.db.models import ObjectFile
from capability_commons.domain.enums import COType
from capability_commons.schemas.objects import CreateObjectRequest, CreateVersionRequest
from capability_commons.services.registry import RegistryService
from capability_commons.storage.adapters import LocalStorageAdapter


@pytest.mark.asyncio
async def test_upload_and_retrieve_file(db_session, workspace):
    """Upload a file, verify DB record, retrieve from storage."""
    svc = RegistryService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-file-{uuid.uuid4().hex[:6]}",
        type=COType.SKILL_GUIDE,
        canonical_title="File Test Object",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="File Test v1",
        plain_language="Test.",
        markdown_body="# Test",
        structured_data={
            "performance_statement": "Test",
            "learning_objectives": ["Test"],
            "steps_summary": ["Test"],
            "success_criteria": ["Test"],
            "failure_modes": ["Test"],
            "safety_boundary": "None",
            "teach_forward": {"three_minute_script": "T", "ten_minute_outline": ["T"], "handout_points": ["T"]},
        },
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = LocalStorageAdapter(root=tmpdir)
        key = uuid.uuid4().hex
        data = b"PNG fake image data for testing"
        adapter.put(key, data, "image/png")

        import hashlib
        checksum = hashlib.sha256(data).hexdigest()

        obj_file = ObjectFile(
            context_object_version_id=ver.id,
            object_store_key=key,
            media_type="image/png",
            byte_size=len(data),
            checksum=checksum,
            label="test-diagram",
        )
        db_session.add(obj_file)
        await db_session.flush()
        await db_session.commit()

        # Verify DB record
        result = await db_session.execute(
            select(ObjectFile).where(ObjectFile.context_object_version_id == ver.id)
        )
        files = result.scalars().all()
        assert len(files) == 1
        assert files[0].media_type == "image/png"
        assert files[0].byte_size == len(data)
        assert files[0].checksum == checksum

        # Verify storage retrieval
        retrieved = adapter.get(key)
        assert retrieved == data


@pytest.mark.asyncio
async def test_delete_file_record(db_session, workspace):
    """Deleting a file should remove the DB record."""
    svc = RegistryService(db_session)

    obj = await svc.create_object(CreateObjectRequest(
        workspace_id=workspace.id,
        slug=f"test-file-del-{uuid.uuid4().hex[:6]}",
        type=COType.CONCEPT_NOTE,
        canonical_title="File Delete Test",
    ))
    ver = await svc.create_version(obj.id, CreateVersionRequest(
        title="Delete Test v1", plain_language="Test.", markdown_body="# Test",
        structured_data={"definition": "Test."},
    ))

    obj_file = ObjectFile(
        context_object_version_id=ver.id,
        object_store_key=uuid.uuid4().hex,
        media_type="text/plain",
        byte_size=5,
        label="delete-me",
    )
    db_session.add(obj_file)
    await db_session.flush()
    file_id = obj_file.id

    await db_session.delete(obj_file)
    await db_session.commit()

    result = await db_session.execute(
        select(ObjectFile).where(ObjectFile.id == file_id)
    )
    assert result.scalar_one_or_none() is None
```

- [ ] **Step 2: Update CI to run storage integration tests**

In `.github/workflows/ci.yml`, add `tests/test_integration_storage.py` to both the ignore list and the integration run list (same pattern as previous tasks).

- [ ] **Step 3: Run integration tests (requires live Postgres)**

Run: `pytest tests/test_integration_storage.py -v`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_storage.py .github/workflows/ci.yml
git commit -m "test(storage): add integration tests and update CI"
```

---

### Task 7: Update Documentation

**Files:**
- Modify: `STATUS.md`
- Modify: `TODO.md`

- [ ] **Step 1: Update STATUS.md**

Add to the route module table:
```
| Files | 4 (upload, list, download, delete) | Production-ready |
```

Update endpoint count (add 4 more: 51 + 4 = 55 if audit was also added, or count from current).
Update table count to include `object_files`.
Update migration count to include the new migration.

In the services table, update the storage entry:
```
| `LocalStorageAdapter` | Local filesystem file storage with hash-prefix directories | Fully implemented |
```

Add `data/files/` to the `.gitignore` if not already present.

- [ ] **Step 2: Update TODO.md**

Mark the storage items as done:
```
- [x] **Implement storage adapter** — `StorageAdapter` ABC with `LocalStorageAdapter` (hash-prefix dirs) and `S3StorageAdapter` stub. Config via `STORAGE_BACKEND`, `STORAGE_ROOT`, `STORAGE_MAX_FILE_SIZE`.
- [x] **Object file management** — CRUD routes at `/v1/objects/{id}/versions/{vid}/files` for upload (multipart), list, download, delete. SHA-256 checksums, media type allowlist, size limits.
```

- [ ] **Step 3: Commit**

```bash
git add STATUS.md TODO.md .gitignore
git commit -m "docs: update STATUS.md and TODO.md for storage adapter"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run the full unit test suite**

Run: `pytest tests/ --ignore=tests/test_integration.py --ignore=tests/test_integration_embedding.py --ignore=tests/test_integration_publication.py --ignore=tests/test_integration_search.py --ignore=tests/test_integration_retrieval.py --ignore=tests/test_integration_audit.py --ignore=tests/test_integration_storage.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run all integration tests (requires live Postgres)**

Run: `pytest tests/test_integration.py tests/test_integration_embedding.py tests/test_integration_publication.py tests/test_integration_search.py tests/test_integration_retrieval.py tests/test_integration_audit.py tests/test_integration_storage.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "test: fix any storage integration test issues"
```
