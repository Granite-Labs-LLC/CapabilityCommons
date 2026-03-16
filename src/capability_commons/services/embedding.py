"""Embedding pipeline: pluggable provider with OpenAI default."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContentSegment


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int = 1536) -> None:
        self.model = model
        self.dimensions = dimensions
        import openai
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            input=texts,
            model=self.model,
            dimensions=self.dimensions,
        )
        return [item.embedding for item in response.data]


class EmbeddingService:
    def __init__(self, session: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        if provider is None:
            from capability_commons.config import get_settings
            settings = get_settings()
            if settings.openai_api_key:
                self.provider = OpenAIEmbeddingProvider(
                    api_key=settings.openai_api_key,
                    model=settings.embedding_model,
                    dimensions=settings.embedding_dim,
                )
            else:
                self.provider = None
        else:
            self.provider = provider

    async def embed_version(self, version_id: uuid.UUID, batch_size: int = 50) -> int:
        if self.provider is None:
            return 0

        result = await self.session.execute(
            select(ContentSegment)
            .where(
                ContentSegment.context_object_version_id == version_id,
                ContentSegment.embedding.is_(None),
            )
            .order_by(ContentSegment.ordinal.asc())
        )
        segments = list(result.scalars().all())

        if not segments:
            return 0

        count = 0
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            texts = [seg.text_content for seg in batch]
            embeddings = await self.provider.embed(texts)
            for seg, emb in zip(batch, embeddings):
                seg.embedding = emb
                seg.metadata_json = {**seg.metadata_json, "embedding_status": "complete"}
            count += len(batch)

        await self.session.flush()
        await self.session.commit()
        return count
