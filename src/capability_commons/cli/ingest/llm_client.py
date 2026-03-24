"""OpenAI-compatible LLM client with Pydantic validation and retry."""
from __future__ import annotations

import json
import os
from typing import TypeVar

import tiktoken
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Raised when LLM output fails validation after all retries."""

    def __init__(self, last_response: str, last_error: str, retries: int) -> None:
        self.last_response = last_response
        self.last_error = last_error
        self.retries = retries
        super().__init__(
            f"LLM output failed validation after {retries} retries. "
            f"Last error: {last_error}"
        )


class LLMClient:
    """Async LLM client that validates responses against Pydantic models."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        model: str = "gpt-4o",
        temperature: float = 0.2,
    ) -> None:
        self.model = model
        self.temperature = temperature
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = AsyncOpenAI(base_url=base_url, api_key=resolved_key)

        # Set up tiktoken encoder with fallback
        try:
            self._encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoder = tiktoken.get_encoding("cl100k_base")

    async def generate(
        self,
        system: str,
        user: str,
        response_model: type[T],
        max_retries: int = 3,
    ) -> T:
        """Send a chat completion request and validate the response.

        On validation failure, retries with the error appended to the
        conversation. Raises LLMValidationError after max_retries failures.
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user + "\n\nRespond with valid JSON only."},
        ]
        last_response = ""
        last_error = ""

        for attempt in range(1 + max_retries):
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            raw = response.choices[0].message.content
            last_response = raw

            try:
                parsed = json.loads(raw)
                return response_model.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)
                if attempt < max_retries:
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": f"JSON validation failed: {last_error}. "
                        "Fix the output and return valid JSON.",
                    })

        raise LLMValidationError(last_response, last_error, max_retries)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        return len(self._encoder.encode(text))
