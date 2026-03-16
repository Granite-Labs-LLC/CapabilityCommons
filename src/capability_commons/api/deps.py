from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.db.session import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return uuid.UUID(value)


async def get_actor_id(x_actor_id: Annotated[str | None, Header()] = None) -> uuid.UUID | None:
    return _parse_uuid(x_actor_id)


async def get_current_workspace(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> Workspace:
    settings = get_settings()
    if not settings.auth_enabled:
        # In dev mode without auth, use X-Workspace-Id header or raise
        ws_id = request.headers.get("x-workspace-id")
        if ws_id is None:
            raise HTTPException(status_code=401, detail="Missing X-Workspace-Id header (auth disabled)")
        ws = await session.get(Workspace, uuid.UUID(ws_id))
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_key = authorization[7:]  # Strip "Bearer "
    from capability_commons.api.auth import resolve_api_key

    result = await resolve_api_key(session, raw_key)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    api_key, workspace = result

    # Store key_hash on request state for rate limiting
    request.state.api_key_hash = api_key.key_hash
    return workspace


DBSession = Annotated[AsyncSession, Depends(get_db)]
ActorID = Annotated[uuid.UUID | None, Depends(get_actor_id)]
CurrentWorkspace = Annotated[Workspace, Depends(get_current_workspace)]
