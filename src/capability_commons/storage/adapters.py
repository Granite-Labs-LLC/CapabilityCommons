"""Storage adapters for file attachments."""
from __future__ import annotations

import abc
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
