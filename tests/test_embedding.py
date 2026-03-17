import pytest
from unittest.mock import AsyncMock

from capability_commons.services.embedding import EmbeddingProvider, EmbeddingService


class FakeProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 10 for _ in texts]


@pytest.mark.asyncio
async def test_embed_version_no_provider():
    session = AsyncMock()
    service = EmbeddingService(session, provider=None)
    service.provider = None  # Ensure no provider
    result = await service.embed_version("fake-id")
    assert result == 0


def test_fake_provider_returns_correct_count():
    import asyncio
    provider = FakeProvider()
    result = asyncio.run(provider.embed(["hello", "world"]))
    assert len(result) == 2
    assert len(result[0]) == 10


@pytest.mark.asyncio
async def test_embed_query_with_provider():
    session = AsyncMock()
    provider = FakeProvider()
    service = EmbeddingService(session, provider=provider)
    result = await service.embed_query("test query")
    assert result is not None
    assert len(result) == 10


@pytest.mark.asyncio
async def test_embed_query_no_provider():
    session = AsyncMock()
    service = EmbeddingService(session, provider=None)
    service.provider = None
    result = await service.embed_query("test query")
    assert result is None
