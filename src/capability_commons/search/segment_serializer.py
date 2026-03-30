"""Serialize structured_data fields into retrieval-friendly text segments."""
from __future__ import annotations

from typing import Any


# Fields to extract from structured_data, keyed by their label for retrieval
IMPLEMENTATION_FIELDS = [
    ("tools", "Tools"),
    ("materials", "Materials"),
    ("success_criteria", "Success criteria"),
    ("stop_conditions", "Stop conditions"),
    ("escalation_guidance", "When to get professional help"),
    ("failure_modes", "Common failure modes"),
    ("safety_boundary", "Safety boundaries"),
    ("variants", "Variants"),
    ("preflight_checks", "Before you start"),
    ("smallest_viable_version", "Simplest version"),
    ("common_mistakes", "Common mistakes"),
    ("time_estimate", "Estimated time"),
    ("cost_estimate", "Estimated cost"),
]


def serialize_structured_data(structured_data: dict[str, Any] | None) -> str:
    """Convert structured_data implementation fields into retrieval text.

    Returns a newline-separated block of labeled fields suitable for
    chunking alongside markdown_body.
    """
    if not structured_data:
        return ""

    parts: list[str] = []
    for key, label in IMPLEMENTATION_FIELDS:
        value = structured_data.get(key)
        if not value:
            continue
        if isinstance(value, list):
            items = ", ".join(str(v) for v in value)
            parts.append(f"{label}: {items}")
        elif isinstance(value, dict):
            items = "; ".join(f"{k}: {v}" for k, v in value.items())
            parts.append(f"{label}: {items}")
        else:
            parts.append(f"{label}: {value}")

    return "\n".join(parts)


def build_indexable_text(
    *,
    markdown_body: str | None,
    plain_language: str | None,
    structured_data: dict[str, Any] | None,
    title: str | None = None,
) -> str:
    """Build the full indexable text from all relevant version fields."""
    parts: list[str] = []
    if title:
        parts.append(title)
    if plain_language:
        parts.append(plain_language)
    if markdown_body:
        parts.append(markdown_body)
    impl_text = serialize_structured_data(structured_data)
    if impl_text:
        parts.append(impl_text)
    return "\n\n".join(parts)
