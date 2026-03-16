from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings
from capability_commons.db.models import Workspace
from capability_commons.domain.enums import WorkspaceVisibility


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()

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
    return ws
