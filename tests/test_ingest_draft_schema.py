"""Tests for the strict canonical-object draft schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_commons.cli.ingest.draft import DraftObject, REQUIRED_BODY_SECTIONS


VALID_BODY = "\n".join(f"## {s}\nSomething" for s in REQUIRED_BODY_SECTIONS)


def _minimal_kwargs(**overrides):
    base = {
        "id": "water.safe-storage",
        "slug": "water.safe-storage",
        "seed_type": "skill",
        "co_type": "skill_guide",
        "canonical_title": "Safe Water Storage",
        "primary_domain": "water",
        "stage": "household",
        "difficulty": 2,
        "cost_band": "low",
        "risk_band": "low",
        "summary_short": "x",
        "summary_medium": "y",
        "plain_language": "z",
        "markdown_body": VALID_BODY,
        "structured_data": {"tools": []},
    }
    base.update(overrides)
    return base


def test_minimal_valid_object_parses():
    obj = DraftObject(**_minimal_kwargs())
    assert obj.slug == "water.safe-storage"


@pytest.mark.parametrize(
    "missing",
    [
        "co_type",
        "primary_domain",
        "stage",
        "difficulty",
        "cost_band",
        "risk_band",
        "summary_short",
        "structured_data",
    ],
)
def test_missing_required_field_rejected(missing: str):
    kwargs = _minimal_kwargs()
    kwargs.pop(missing)
    with pytest.raises(ValidationError):
        DraftObject(**kwargs)


def test_markdown_body_missing_sections_rejected():
    bad_body = "## What this is\nSomething.\n## Why it matters\nReason."
    with pytest.raises(ValidationError) as ei:
        DraftObject(**_minimal_kwargs(markdown_body=bad_body))
    assert "missing required sections" in str(ei.value)


def test_difficulty_out_of_range_rejected():
    with pytest.raises(ValidationError):
        DraftObject(**_minimal_kwargs(difficulty=6))


def test_invalid_enum_value_rejected():
    with pytest.raises(ValidationError):
        DraftObject(**_minimal_kwargs(co_type="not-a-real-type"))
