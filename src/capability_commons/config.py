from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = "dev"
    app_name: str = "Capability Commons API"
    api_v1_prefix: str = "/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/capability_commons"
    database_echo: bool = False

    # Connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True

    embedding_dim: int = 1536
    default_top_k: int = 20
    default_max_graph_depth: int = 3
    default_max_iterations: int = 4
    default_sufficiency_threshold: float = 0.75
    public_preview: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4321"])

    # Auth
    auth_enabled: bool = True
    rate_limit_per_minute: int = 100
    rate_limit_public_per_minute: int = 60

    # Embeddings
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 50

    # Observability
    sentry_dsn: str = ""
    metrics_enabled: bool = True

    # Worker
    outbox_poll_interval_seconds: float = 2.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
