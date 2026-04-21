"""Tests for the storage adapter and file routes."""
from __future__ import annotations

import tempfile

import pytest


def test_storage_settings_exist():
    """Config should have storage settings."""
    from capability_commons.config import Settings

    fields = Settings.model_fields
    assert "storage_backend" in fields
    assert "storage_root" in fields
    assert "storage_max_file_size" in fields


def test_storage_adapter_abc():
    """StorageAdapter should define put, get, delete, exists."""
    import abc

    from capability_commons.storage.adapters import StorageAdapter

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

    with tempfile.TemporaryDirectory() as tmpdir:
        adapter = LocalStorageAdapter(root=tmpdir)
        with pytest.raises(FileNotFoundError):
            adapter.get("nonexistent")


def test_s3_adapter_raises_not_implemented():
    """S3StorageAdapter methods should raise NotImplementedError."""
    from capability_commons.storage.adapters import S3StorageAdapter

    adapter = S3StorageAdapter()
    with pytest.raises(NotImplementedError):
        adapter.put("key", b"data", "text/plain")
    with pytest.raises(NotImplementedError):
        adapter.get("key")
    with pytest.raises(NotImplementedError):
        adapter.delete("key")
    with pytest.raises(NotImplementedError):
        adapter.exists("key")


def test_file_metadata_schema():
    """FileMetadataResponse should have expected fields."""
    from capability_commons.schemas.files import FileMetadataResponse

    fields = FileMetadataResponse.model_fields
    expected = {"id", "object_store_key", "media_type", "byte_size", "checksum", "label", "created_at"}
    assert expected.issubset(set(fields.keys())), f"Missing: {expected - set(fields.keys())}"


def test_file_routes_wired():
    """File routes should be wired and return 401 (not 404) without auth."""
    import uuid

    from fastapi.testclient import TestClient

    from capability_commons.main import app

    client = TestClient(app)
    oid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    fid = str(uuid.uuid4())

    r = client.post(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    r = client.get(f"/v1/objects/{oid}/versions/{vid}/files")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    r = client.get(f"/v1/objects/{oid}/versions/{vid}/files/{fid}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    r = client.delete(f"/v1/objects/{oid}/versions/{vid}/files/{fid}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
