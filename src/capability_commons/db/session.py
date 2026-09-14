from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.config import get_settings

settings = get_settings()
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_engine_loop: asyncio.AbstractEventLoop | None = None


async def ensure_engine_for_running_loop() -> None:
    """Detach the connection pool if it was filled under a different event loop.

    `engine` is a module-level singleton and asyncpg connections are bound to
    the loop that opened them. Anything that drives the app from more than one
    loop in a process -- notably `TestClient(app)` used without a `with` block,
    which runs each request on a fresh loop -- would otherwise be handed a
    pooled connection from a closed loop ("Event loop is closed" / "attached to
    a different loop"). Under uvicorn there is one loop, so this is a cheap
    identity check per session.
    """
    global _engine_loop
    loop = asyncio.get_running_loop()
    if _engine_loop is loop:
        return
    if _engine_loop is not None:
        # close=False: the old connections belong to a loop that may be gone,
        # so drop them without trying to close them from this one.
        await engine.dispose(close=False)
    _engine_loop = loop


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    await ensure_engine_for_running_loop()
    async with SessionLocal() as session:
        yield session
