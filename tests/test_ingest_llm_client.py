"""Tests for LLM client with Pydantic validation and retry."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from capability_commons.cli.ingest.llm_client import LLMClient, LLMValidationError


class SimpleResponse(BaseModel):
    name: str
    score: float


class TestLLMClientGenerate:
    @pytest.fixture
    def client(self):
        return LLMClient(
            base_url="https://api.test.com/v1",
            api_key="test-key",
            model="test-model",
        )

    async def test_successful_generation(self, client):
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content=json.dumps({"name": "test", "score": 0.9})))
        ]
        mock_create = AsyncMock(return_value=mock_response)
        with patch.object(client._client.chat.completions, "create", new=mock_create):
            result = await client.generate(
                system="You are a test.",
                user="Return a name and score.",
                response_model=SimpleResponse,
            )
        assert result.name == "test"
        assert result.score == 0.9

    async def test_retry_on_validation_failure(self, client):
        bad_response = AsyncMock()
        bad_response.choices = [
            AsyncMock(message=AsyncMock(content=json.dumps({"name": "test"})))  # missing score
        ]
        good_response = AsyncMock()
        good_response.choices = [
            AsyncMock(message=AsyncMock(content=json.dumps({"name": "test", "score": 0.5})))
        ]
        mock_create = AsyncMock(side_effect=[bad_response, good_response])
        with patch.object(client._client.chat.completions, "create", new=mock_create):
            result = await client.generate(
                system="test",
                user="test",
                response_model=SimpleResponse,
            )
        assert result.score == 0.5

    async def test_raises_after_max_retries(self, client):
        bad_response = AsyncMock()
        bad_response.choices = [
            AsyncMock(message=AsyncMock(content="not json at all"))
        ]
        mock_create = AsyncMock(return_value=bad_response)
        with patch.object(client._client.chat.completions, "create", new=mock_create):
            with pytest.raises(LLMValidationError):
                await client.generate(
                    system="test",
                    user="test",
                    response_model=SimpleResponse,
                    max_retries=2,
                )


class TestLLMClientEstimateTokens:
    def test_estimate_returns_positive(self):
        client = LLMClient(
            base_url="https://api.test.com/v1",
            api_key="test-key",
            model="gpt-4o",
        )
        count = client.estimate_tokens("Hello, this is a test message.")
        assert count > 0
        assert isinstance(count, int)

    def test_estimate_fallback_for_unknown_model(self):
        client = LLMClient(
            base_url="https://api.test.com/v1",
            api_key="test-key",
            model="some-local-model",
        )
        count = client.estimate_tokens("Hello, this is a test message.")
        assert count > 0  # Falls back to cl100k_base
