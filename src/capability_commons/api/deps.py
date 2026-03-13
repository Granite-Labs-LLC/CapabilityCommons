from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

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


DBSession = Annotated[AsyncSession, Depends(get_db)]
ActorID = Annotated[uuid.UUID | None, Depends(get_actor_id)]
