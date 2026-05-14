"""Tests for the strict publish-readiness gate (PLAN P1-8)."""
from __future__ import annotations

import yaml

from capability_commons.cli.ingest.project import IngestProject
from capability_commons.cli.ingest.validate import run_validate


def _project(tmp_path):
    return IngestProject.init(
        projects_root=tmp_path / "projects",
        name="test-publish-gate",
        sources=[{"id": "src.test", "file": "sources/x.pdf",
                  "title": "T", "source_kind": "BOOK"}],
    )


_VALID_ENVELOPE = {
    "smallest_viable_version": "Pour 1 gallon into a clean food-grade jug.",
    "stop_conditions": ["Container smells off."],
    "success_checks": ["Jug is sealed."],
}


def _draft(**overrides):
    base = {
        "slug": "water.x",
        "canonical_title": "X",
        "co_type": "skill_guide",
        "stage": "household",
        "cost_band": "low",
        "risk_band": "low",
        "plain_language": "px",
        "markdown_body": "# Body\n\nstuff",
        "lifecycle_state": "published",
        "citations": [
            {"claim_id": "clm_001", "claim_text": "a", "source_id": "src.test"},
            {"claim_id": "clm_002", "claim_text": "b", "source_id": "src.test"},
        ],
        "structured_data": {"tools": [], "implementation": _VALID_ENVELOPE},
    }
    base.update(overrides)
    return base


def _write(project, **overrides):
    draft = _draft(**overrides)
    with open(project.drafts_dir / f"{draft['slug']}.yaml", "w") as f:
        yaml.dump(draft, f)


def test_strict_passes_when_envelope_and_citations_present(tmp_path):
    project = _project(tmp_path)
    _write(project)
    report = run_validate(project, strict=True)
    assert report.publish_blockers == []
    assert all("publish" not in e.lower() for e in report.errors)


def test_strict_blocks_when_fewer_than_two_citations(tmp_path):
    project = _project(tmp_path)
    _write(project, citations=[
        {"claim_id": "clm_001", "claim_text": "a", "source_id": "src.test"}
    ])
    report = run_validate(project, strict=True)
    assert any("at least 2 citations" in b for b in report.publish_blockers)
    # Blockers must also surface as errors so load() refuses.
    assert any("at least 2 citations" in e for e in report.errors)


def test_strict_blocks_actionable_without_envelope(tmp_path):
    project = _project(tmp_path)
    _write(project, structured_data={"tools": []})  # no implementation
    report = run_validate(project, strict=True)
    assert any("requires structured_data.implementation" in b
                for b in report.publish_blockers)


def test_strict_blocks_envelope_missing_required_fields(tmp_path):
    project = _project(tmp_path)
    _write(project, structured_data={
        "implementation": {
            "smallest_viable_version": "do x",
            # missing stop_conditions and success_checks
        }
    })
    report = run_validate(project, strict=True)
    assert any("envelope missing" in b for b in report.publish_blockers)


def test_strict_blocks_high_risk_without_safety(tmp_path):
    project = _project(tmp_path)
    # Concept_note skips the envelope requirement but still must have safety
    # boundary at risk=high.
    _write(project, slug="water.dangerous", co_type="concept_note",
           risk_band="high", structured_data={"definition": "x"})
    report = run_validate(project, strict=True)
    # The non-strict path already blocks high-risk without safety_boundary,
    # so it surfaces as an error AND a publish blocker.
    assert any("safety" in e.lower() for e in report.errors)
    assert any("safety" in b.lower() for b in report.publish_blockers)


def test_non_published_drafts_skip_publish_gate(tmp_path):
    project = _project(tmp_path)
    # Same shape as the failing-citation case but lifecycle is draft.
    _write(project, lifecycle_state="draft", citations=[])
    report = run_validate(project, strict=True)
    assert report.publish_blockers == []


def test_non_strict_does_not_emit_publish_blockers(tmp_path):
    project = _project(tmp_path)
    _write(project, citations=[])  # would block under strict
    report = run_validate(project)  # default strict=False
    assert report.publish_blockers == []


def test_validator_accepts_source_id_inside_support_spans(tmp_path):
    """Post-cite-pass citations have shape:
        {claim_id, claim_text, support: [{source_id, segment_id, ...}]}
    so a top-level `source_id` is absent. The validator must NOT warn on
    that shape — only when neither location has it."""
    project = _project(tmp_path)
    _write(project, citations=[
        {
            "claim_id": "clm_001",
            "claim_text": "x",
            "support": [{
                "source_id": "src.test",
                "segment_id": "src.test::seg_000001",
                "excerpt": "evidence",
                "page_start": 1, "page_end": 1,
                "start_char": 0, "end_char": 8,
                "support_strength": "strong",
            }],
        },
        {
            "claim_id": "clm_002",
            "claim_text": "y",
            "support": [{
                "source_id": "src.test",
                "segment_id": "src.test::seg_000002",
                "excerpt": "more evidence",
                "page_start": 2, "page_end": 2,
                "start_char": 0, "end_char": 13,
                "support_strength": "strong",
            }],
        },
    ])
    report = run_validate(project)
    assert not any("missing source_id" in w for w in report.warnings)


def test_validator_warns_when_neither_top_level_nor_support_has_source_id(tmp_path):
    project = _project(tmp_path)
    _write(project, citations=[
        {"claim_id": "clm_001", "claim_text": "x",
         "support": [{"segment_id": "x", "excerpt": "y"}]},
    ])
    report = run_validate(project)
    assert any("missing source_id" in w for w in report.warnings)
