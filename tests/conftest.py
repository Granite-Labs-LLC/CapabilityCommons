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
        # Clean up test data by deleting test workspaces (cascades). outbox_events
        # has no foreign keys, so the cascade can't reach it: delete test rows'
        # events first, or they're left pointing at deleted objects. Those
        # orphans can never process and the worker retries them forever
        # (found 2026-09-13; the likely source of the "orphaned version.published
        # events" first seen after the FEMA load).
        await session.execute(
            text(
                """
                DELETE FROM outbox_events WHERE aggregate_id IN (
                    SELECT co.id FROM context_objects co
                    JOIN workspaces w ON w.id = co.workspace_id WHERE w.slug LIKE 'test-%'
                    UNION
                    SELECT v.id FROM context_object_versions v
                    JOIN context_objects co ON co.id = v.context_object_id
                    JOIN workspaces w ON w.id = co.workspace_id WHERE w.slug LIKE 'test-%'
                    UNION
                    SELECT e.id FROM edges e
                    JOIN workspaces w ON w.id = e.workspace_id WHERE w.slug LIKE 'test-%'
                )
                """
            )
        )
        await session.execute(text("DELETE FROM workspaces WHERE slug LIKE 'test-%'"))
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
