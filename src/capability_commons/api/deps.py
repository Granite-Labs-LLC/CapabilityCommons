from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.api.auth import resolve_api_key
from capability_commons.db.session import get_session

PUBLIC_WORKSPACE_SLUG = "capability-commons"


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
        try:
            ws_uuid = uuid.UUID(ws_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid workspace ID format")
        ws = await session.get(Workspace, ws_uuid)
        if ws is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return ws

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    raw_key = authorization[7:]  # Strip "Bearer "
    result = await resolve_api_key(session, raw_key)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    api_key, workspace = result

    # Store key_hash on request state for rate limiting
    request.state.api_key_hash = api_key.key_hash
    return workspace


async def get_public_or_authenticated_workspace(
    request: Request,
    session: AsyncSession = Depends(get_db),
    authorization: Annotated[str | None, Header()] = None,
) -> Workspace:
    """Resolve workspace: authenticated user gets their workspace, anonymous gets the public workspace."""
    settings = get_settings()

    # Try authenticated resolution first if a Bearer token is present
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization[7:]
        result = await resolve_api_key(session, raw_key)
        if result is not None:
            api_key, workspace = result
            request.state.api_key_hash = api_key.key_hash
            return workspace
        # Invalid key — reject rather than falling back to public
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Dev mode: also accept X-Workspace-Id header
    if not settings.auth_enabled:
        ws_id = request.headers.get("x-workspace-id")
        if ws_id is not None:
            try:
                ws_uuid = uuid.UUID(ws_id)
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid workspace ID format")
            ws = await session.get(Workspace, ws_uuid)
            if ws is None:
                raise HTTPException(status_code=404, detail="Workspace not found")
            return ws

    # Anonymous — resolve the public workspace
    row = await session.execute(
        select(Workspace).where(Workspace.slug == PUBLIC_WORKSPACE_SLUG)
    )
    ws = row.scalar_one_or_none()
    if ws is None:
        raise HTTPException(status_code=503, detail="Public workspace not configured")
    return ws


DBSession = Annotated[AsyncSession, Depends(get_db)]
ActorID = Annotated[uuid.UUID | None, Depends(get_actor_id)]
CurrentWorkspace = Annotated[Workspace, Depends(get_current_workspace)]
PublicWorkspace = Annotated[Workspace, Depends(get_public_or_authenticated_workspace)]
