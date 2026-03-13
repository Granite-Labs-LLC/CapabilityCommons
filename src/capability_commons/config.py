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
    embedding_dim: int = 1536
    default_top_k: int = 20
    default_max_graph_depth: int = 3
    default_max_iterations: int = 4
    default_sufficiency_threshold: float = 0.75
    public_preview: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
