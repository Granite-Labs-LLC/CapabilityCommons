from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ApiKey, Workspace


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """Returns (raw_key, key_hash)."""
    raw = f"cc_{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw)


def is_key_expired(expire_at: datetime | None) -> bool:
    """Check if a key has expired. Returns False if no expiry is set."""
    if expire_at is None:
        return False
    return datetime.now(timezone.utc) >= expire_at


async def resolve_api_key(session: AsyncSession, raw_key: str) -> tuple[ApiKey, Workspace] | None:
    key_hash = hash_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if is_key_expired(api_key.expire_at):
        return None
    workspace = await session.get(Workspace, api_key.workspace_id)
    if workspace is None:
        return None
    return api_key, workspace
