"""Integration tests for file storage: upload, list, download, delete via real DB."""
from __future__ import annotations

import hashlib
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
            "teach_forward": {
                "three_minute_script": "T",
                "ten_minute_outline": ["T"],
                "handout_points": ["T"],
            },
        },
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = LocalStorageAdapter(root=tmpdir)
        key = uuid.uuid4().hex
        data = b"PNG fake image data for testing"
        adapter.put(key, data, "image/png")

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

        result = await db_session.execute(
            select(ObjectFile).where(ObjectFile.context_object_version_id == ver.id)
        )
        files = result.scalars().all()
        assert len(files) == 1
        assert files[0].media_type == "image/png"
        assert files[0].byte_size == len(data)
        assert files[0].checksum == checksum

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
        title="Delete Test v1",
        plain_language="Test.",
        markdown_body="# Test",
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
