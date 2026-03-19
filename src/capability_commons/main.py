from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from capability_commons.api.errors import register_error_handlers
from capability_commons.api.logging_middleware import RequestLoggingMiddleware
from capability_commons.api.rate_limit import RateLimitMiddleware
from capability_commons.api.router import api_router
from capability_commons.config import get_settings
from capability_commons.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, session_factory=SessionLocal)
app.include_router(api_router)
