"""Tests for the strict canonical-object draft schema."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_commons.cli.ingest.draft import DraftObject, REQUIRED_BODY_SECTIONS


VALID_BODY = "\n".join(f"## {s}\nSomething" for s in REQUIRED_BODY_SECTIONS)

_VALID_ENVELOPE = {
    "smallest_viable_version": "Pour 1 gallon into a clean food-grade jug.",
    "tools": ["measuring cup"],
    "materials": ["food-grade jug"],
    "expected_time": "10 minutes",
    "expected_cost": "free",
    "success_checks": ["Jug is sealed and labeled with date."],
    "stop_conditions": ["Container smells off."],
    "common_mistakes": ["Reusing milk jugs."],
    "variants": [
        {"label": "renter", "when": "no spigot access", "notes": "use kitchen tap"},
    ],
    "when_to_escalate": ["No clean water source available within 24h."],
}


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
        "structured_data": {"tools": [], "implementation": _VALID_ENVELOPE},
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


def test_skill_guide_requires_implementation_envelope():
    kwargs = _minimal_kwargs(structured_data={"tools": []})  # no implementation
    with pytest.raises(ValidationError) as ei:
        DraftObject(**kwargs)
    assert "structured_data.implementation" in str(ei.value)


def test_project_blueprint_requires_implementation_envelope():
    kwargs = _minimal_kwargs(co_type="project_blueprint",
                              structured_data={"tools": []})
    with pytest.raises(ValidationError):
        DraftObject(**kwargs)


def test_envelope_missing_smallest_viable_version_rejected():
    bad = dict(_VALID_ENVELOPE)
    bad.pop("smallest_viable_version")
    kwargs = _minimal_kwargs(structured_data={"implementation": bad})
    with pytest.raises(ValidationError):
        DraftObject(**kwargs)


def test_concept_note_does_not_require_envelope():
    """Non-actionable types (concept_note, glossary, …) don't need the envelope."""
    kwargs = _minimal_kwargs(co_type="concept_note", structured_data={"definition": "x"})
    obj = DraftObject(**kwargs)
    assert obj.co_type.value == "concept_note"
    assert "implementation" not in obj.structured_data


def test_envelope_normalized_into_structured_data():
    """A valid envelope is parsed and re-serialized so downstream consumers
    see a normalized dict (defaults filled, extra keys preserved)."""
    obj = DraftObject(**_minimal_kwargs())
    impl = obj.structured_data["implementation"]
    assert impl["smallest_viable_version"].startswith("Pour")
    assert impl["variants"][0]["label"] == "renter"
    # Defaults preserved.
    assert isinstance(impl["common_mistakes"], list)
