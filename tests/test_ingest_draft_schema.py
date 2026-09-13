"""Tests for the strict canonical-object draft schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_commons.cli.ingest.draft import (
    IMPLEMENTATION_EXAMPLE,
    REQUIRED_BODY_SECTIONS,
    USER_TEMPLATE,
    DraftObject,
    ImplementationEnvelope,
    _merge_duplicate_slug_rows,
)
from capability_commons.domain.enums import CostBand, RiskBand, StageType

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
    kwargs = _minimal_kwargs(co_type="project_blueprint", structured_data={"tools": []})
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


def test_prompt_implementation_example_is_valid_envelope():
    """The example rendered into the draft prompt must itself pass the
    validator, so the prompt can't drift from what DraftObject requires."""
    ImplementationEnvelope.model_validate(IMPLEMENTATION_EXAMPLE)
    obj = DraftObject.model_validate(_minimal_kwargs(structured_data={"implementation": IMPLEMENTATION_EXAMPLE}))
    assert obj.structured_data["implementation"]["smallest_viable_version"]


def test_prompt_renders_nested_implementation_example():
    rendered = USER_TEMPLATE.format(matrix_row="{}", segments="seg")
    assert '"implementation": {' in rendered
    for field in ImplementationEnvelope.model_fields:
        assert f'"{field}"' in rendered


@pytest.mark.parametrize("enum_cls", [StageType, CostBand, RiskBand])
def test_prompt_lists_exact_enum_values(enum_cls):
    """Enum fields in the prompt are generated from the validator's enums, so
    the model is never told a value (like 'DRAFT' or 'medium') it will reject."""
    rendered = USER_TEMPLATE.format(matrix_row="{}", segments="seg")
    assert "one of " + " | ".join(m.value for m in enum_cls) in rendered


def test_duplicate_slug_rows_merged_before_drafting():
    """Two matrix rows with one slug must become one draft over both segments,
    not two drafts where the second silently overwrites the first."""
    rows = [
        {"candidate_slug": "a", "segment_ids": "seg_1"},
        {"candidate_slug": "b", "segment_ids": "seg_2"},
        {"candidate_slug": "a", "segment_ids": "seg_3|seg_1"},
    ]
    merged = _merge_duplicate_slug_rows(rows)
    assert [r["candidate_slug"] for r in merged] == ["a", "b"]
    assert merged[0]["segment_ids"] == "seg_1|seg_3"
    assert rows[0]["segment_ids"] == "seg_1"  # input rows not mutated
