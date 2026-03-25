from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from capability_commons.api.errors import register_error_handlers
from capability_commons.api.logging_middleware import RequestLoggingMiddleware
from capability_commons.api.rate_limit import RateLimitMiddleware
from capability_commons.api.router import api_router
from capability_commons.config import get_settings
from capability_commons.db.session import SessionLocal

settings = get_settings()

# Structured logging: JSON in production, colored console in dev
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "dev"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# Sentry error tracking (opt-in via SENTRY_DSN env var)
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.1,
        environment=settings.app_env,
    )


def check_pending_migrations() -> None:
    """Log a warning if there are pending Alembic migrations."""
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine

        sync_url = settings.database_url.replace("+asyncpg", "")
        sync_engine = create_engine(sync_url)
        with sync_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_heads = set(context.get_current_heads())
            script = ScriptDirectory.from_config(Config("alembic.ini"))
            expected_heads = set(script.get_heads())
            if current_heads != expected_heads:
                log = structlog.get_logger()
                log.warning(
                    "pending_migrations",
                    current=list(current_heads),
                    expected=list(expected_heads),
                )
        sync_engine.dispose()
    except Exception:
        pass  # Don't block startup if alembic check fails


@asynccontextmanager
async def lifespan(app):
    check_pending_migrations()
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics (opt-out via METRICS_ENABLED=false)
if settings.metrics_enabled:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, session_factory=SessionLocal)
app.include_router(api_router)
