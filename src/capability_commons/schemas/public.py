from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from capability_commons.schemas.common import CitationSnippet


class PublicObjectResponse(BaseModel):
    slug: str
    title: str
    type: str
    summary_short: str | None = None
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    facets: dict[str, list[str]] = Field(default_factory=dict)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[CitationSnippet] = Field(default_factory=list)
    review_summary: dict[str, int] = Field(default_factory=dict)
    contradiction_summary: dict[str, int] = Field(default_factory=dict)
    members: list[dict[str, Any]] = Field(default_factory=list)


class PublicBundleResponse(BaseModel):
    object: PublicObjectResponse
    bundle: dict[str, Any] = Field(default_factory=dict)
