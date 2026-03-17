from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.domain.enums import WorkspaceVisibility


@pytest_asyncio.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        # Clean up test data by deleting test workspaces (cascades)
        await session.execute(
            text("DELETE FROM workspaces WHERE slug LIKE 'test-%'")
        )
        await session.commit()

    await engine.dispose()


@pytest_asyncio.fixture
async def workspace(db_session: AsyncSession):
    ws = Workspace(
        slug=f"test-{uuid.uuid4().hex[:8]}",
        name="Test Workspace",
        visibility=WorkspaceVisibility.PUBLIC,
    )
    db_session.add(ws)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(ws)
    return ws
