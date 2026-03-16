from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from capability_commons.config import get_settings
from capability_commons.db.models import RateLimitLog


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_factory: async_sessionmaker):
        super().__init__(app)
        self.session_factory = session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Skip rate limiting if auth is disabled
        if not settings.auth_enabled:
            return await call_next(request)

        # Determine key: API key hash if authenticated, or IP for public routes
        is_public = request.url.path.startswith("/v1/public/") or request.url.path == "/health"
        key_hash = getattr(request.state, "api_key_hash", None)

        if key_hash is None and not is_public:
            # No key and not public — auth middleware will handle rejection
            return await call_next(request)

        if key_hash is None:
            # Public route — rate limit by IP
            client_ip = request.client.host if request.client else "unknown"
            key_hash = f"ip:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
            limit = settings.rate_limit_public_per_minute
        else:
            limit = settings.rate_limit_per_minute

        # Current minute window
        now = datetime.now(timezone.utc)
        window_start = now.replace(second=0, microsecond=0)

        async with self.session_factory() as session:
            # Upsert with increment
            stmt = pg_insert(RateLimitLog).values(
                key_hash=key_hash,
                window_start=window_start,
                request_count=1,
            ).on_conflict_do_update(
                constraint="uq_rate_limit_key_window",
                set_={"request_count": RateLimitLog.request_count + 1},
            ).returning(RateLimitLog.request_count)

            result = await session.execute(stmt)
            count = result.scalar_one()
            await session.commit()

        if count > limit:
            retry_after = 60 - now.second
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
