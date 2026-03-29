# Phase 0: Correctness Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix ingestion correctness, provenance, graph semantics, publish/index flow, and access control so a real multi-source ingest run works end-to-end.

**Architecture:** Fix bugs in the existing pipeline without changing the overall structure. Normalize enum casing at write boundaries, add metadata_json to EvidenceSpan via migration, make seed_graph emit outbox events so the worker indexes/embeds published content, and lock down retrieval run endpoints.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, Pydantic v2, PostgreSQL/pgvector, pytest

---

## File Map

| Ticket | Files Modified | Files Created |
|--------|---------------|---------------|
| ING-001 | `src/capability_commons/cli/ingest/load.py`, `src/capability_commons/cli/ingest/validate.py`, `src/capability_commons/cli/seed.py` | - |
| ING-002 | `src/capability_commons/cli/ingest/parse.py`, `src/capability_commons/cli/ingest/models.py` | - |
| ING-003 | `src/capability_commons/cli/ingest/parse.py`, `src/capability_commons/cli/ingest/models.py`, `src/capability_commons/cli/ingest/extract.py`, `src/capability_commons/cli/ingest/draft.py`, `src/capability_commons/cli/ingest/cite.py` | - |
| ING-004 | `src/capability_commons/cli/ingest/draft.py`, `src/capability_commons/cli/ingest/models.py` | `src/capability_commons/cli/ingest/canonical_schema.py` |
| ING-005 | `src/capability_commons/cli/ingest/canonicalize.py`, `src/capability_commons/cli/ingest/models.py` | - |
| SEED-001 | `src/capability_commons/cli/seed.py` | - |
| SEED-002 | `src/capability_commons/db/models.py` | `alembic/versions/20260329_0001_evidence_span_metadata.py` |
| PUB-001 | `src/capability_commons/cli/seed.py` | - |
| API-SEC-001 | `src/capability_commons/api/routes/retrieval.py` | - |
| TEST-001 | - | `tests/test_phase0_regression.py` |

---

### Task 1: ING-001 — Normalize lifecycle enum casing

**Files:**
- Modify: `src/capability_commons/cli/ingest/load.py:54-58`
- Modify: `src/capability_commons/cli/ingest/validate.py:23`
- Modify: `src/capability_commons/cli/seed.py:209-210`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test for lifecycle casing in load.py**

```python
# tests/test_phase0_regression.py
"""Regression tests for Phase 0 correctness fixes."""
from __future__ import annotations

import yaml
import pytest

from capability_commons.cli.ingest.models import ValidationReport
from capability_commons.cli.ingest.parse import markdown_to_segments
from capability_commons.domain.enums import LifecycleState


class TestING001LifecycleCasing:
    def test_load_writes_lowercase_lifecycle(self, tmp_path):
        """ING-001: load.py must write lowercase lifecycle_state values."""
        from capability_commons.cli.ingest.project import IngestProject

        proj = IngestProject.init(
            projects_root=tmp_path / "projects",
            name="test-casing",
            sources=[{"id": "src.test", "file": "sources/test.md", "title": "Test", "source_kind": "BOOK"}],
        )
        # Create a draft YAML
        draft_path = proj.drafts_dir / "test-obj.yaml"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        with open(draft_path, "w") as f:
            yaml.dump({"id": "test-obj", "slug": "test-obj", "canonical_title": "Test", "markdown_body": "body"}, f)

        # Import and call the publish-patching logic
        from capability_commons.cli.ingest.load import _patch_lifecycle
        _patch_lifecycle(proj.drafts_dir)

        with open(draft_path) as f:
            obj = yaml.safe_load(f)
        assert obj["lifecycle_state"] == "published"
        # Must be parseable by the enum
        assert LifecycleState(obj["lifecycle_state"]) == LifecycleState.PUBLISHED

    def test_validate_accepts_lowercase_lifecycle(self):
        """ING-001: validator must accept canonical lowercase lifecycle values."""
        from capability_commons.cli.ingest.validate import VALID_LIFECYCLE
        assert "published" in VALID_LIFECYCLE
        assert "draft" in VALID_LIFECYCLE
        assert "PUBLISHED" not in VALID_LIFECYCLE

    def test_seed_resolves_lowercase_lifecycle(self):
        """ING-001: seed_graph must handle lowercase lifecycle_state from YAML."""
        node = {"lifecycle_state": "published"}
        lifecycle_str = node.get("lifecycle_state", "published")
        lifecycle = LifecycleState(lifecycle_str)
        assert lifecycle == LifecycleState.PUBLISHED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING001LifecycleCasing -v --no-header 2>&1 | head -30`
Expected: FAIL — `_patch_lifecycle` doesn't exist; VALID_LIFECYCLE has uppercase values

- [ ] **Step 3: Fix load.py — extract publish patching into a function, use lowercase**

In `src/capability_commons/cli/ingest/load.py`, replace the publish block (lines 53-60):

```python
def _patch_lifecycle(drafts_dir: Path) -> None:
    """Set lifecycle_state to canonical lowercase 'published' on all drafts."""
    for draft_file in sorted(drafts_dir.glob("*.yaml")):
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        obj["lifecycle_state"] = "published"
        with open(draft_file, "w") as f:
            yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
```

Update `run_load` to call `_patch_lifecycle(project.drafts_dir)` and change the print to `"Setting lifecycle_state=published..."`.

- [ ] **Step 4: Fix validate.py — use lowercase lifecycle values**

In `src/capability_commons/cli/ingest/validate.py`, change line 23:

```python
VALID_LIFECYCLE = {"draft", "in_review", "reviewed", "verified", "published", "deprecated", "archived"}
```

- [ ] **Step 5: Fix seed.py — default to lowercase, handle both casings**

In `src/capability_commons/cli/seed.py`, change line 209:

```python
lifecycle_str = node.get("lifecycle_state", "published").lower()
lifecycle = LifecycleState(lifecycle_str) if lifecycle_str else LifecycleState.PUBLISHED
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING001LifecycleCasing -v --no-header`
Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add tests/test_phase0_regression.py src/capability_commons/cli/ingest/load.py src/capability_commons/cli/ingest/validate.py src/capability_commons/cli/seed.py
git commit -m "fix(ING-001): normalize lifecycle enum casing to lowercase"
```

---

### Task 2: ING-002 — True page-preserving parse output

**Files:**
- Modify: `src/capability_commons/cli/ingest/parse.py:33-88`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test for page-preserving segments**

```python
class TestING002PagePreservingParse:
    def test_multipage_segments_have_correct_pages(self):
        """ING-002: segments from multi-page source must have real page_start/page_end."""
        md = (
            "<!-- PAGE 1 -->\n"
            "# Chapter 1\n\nContent on page 1.\n\n"
            "<!-- PAGE 2 -->\n"
            "More content on page 2.\n\n"
            "## Section 1.1\n\nSection on page 2.\n\n"
            "<!-- PAGE 3 -->\n"
            "# Chapter 2\n\nContent on page 3.\n"
        )
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        # Chapter 1 starts on page 1, spans to page 2
        ch1 = segments[0]
        assert ch1.page_start == 1
        assert ch1.page_end >= 2  # spans across the page break

        # Chapter 2 starts on page 3
        ch2 = [s for s in segments if "Chapter 2" in s.heading_path[-1]]
        assert len(ch2) == 1
        assert ch2[0].page_start == 3

    def test_no_page_markers_uses_base_page(self):
        """ING-002: without page markers, segments default to base_page."""
        md = "# Heading\nSome text."
        segments = markdown_to_segments(md, source_id="src.test", base_page=5)
        assert segments[0].page_start == 5
        assert segments[0].page_end == 5

    def test_segments_without_headings_track_pages(self):
        """ING-002: even without headings, page markers update the page."""
        md = "<!-- PAGE 1 -->\nParagraph one.\n<!-- PAGE 2 -->\nParagraph two.\n"
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        assert len(segments) >= 1
        # Single segment should span pages 1-2
        assert segments[0].page_start == 1
        assert segments[0].page_end == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING002PagePreservingParse -v --no-header 2>&1 | head -20`
Expected: FAIL — current code stamps all segments with base_page

- [ ] **Step 3: Implement page-tracking in markdown_to_segments**

Replace `markdown_to_segments` in `src/capability_commons/cli/ingest/parse.py`:

```python
def markdown_to_segments(
    markdown: str,
    source_id: str,
    base_page: int = 1,
) -> list[SourceSegment]:
    """Split markdown into segments at heading boundaries with page tracking.

    Page markers are HTML comments like <!-- PAGE N --> inserted by the PDF
    converter or manually. If no markers are present, all segments default
    to base_page.
    """
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    page_re = re.compile(r"<!--\s*PAGE\s+(\d+)\s*-->", re.IGNORECASE)
    segments: list[SourceSegment] = []

    # Build page map: char_offset -> page_number
    page_breaks: list[tuple[int, int]] = []
    for m in page_re.finditer(markdown):
        page_breaks.append((m.start(), int(m.group(1))))

    def _page_at(char_pos: int) -> int:
        """Return the page number at a given character position."""
        page = base_page
        for offset, pg in page_breaks:
            if offset <= char_pos:
                page = pg
            else:
                break
        return page

    # Find all heading positions
    splits: list[tuple[int, list[str]]] = []
    heading_stack: list[str] = []

    for match in heading_re.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        splits.append((match.start(), list(heading_stack)))

    if not splits:
        if markdown.strip():
            text = markdown.strip()
            segments.append(SourceSegment(
                source_id=source_id,
                segment_id="seg_000001",
                page_start=_page_at(0),
                page_end=_page_at(len(markdown) - 1),
                heading_path=[],
                text=text,
                start_char=0,
                end_char=len(text),
            ))
        return segments

    for i, (start, heading_path) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(markdown)
        text = markdown[start:end].strip()
        if not text:
            continue

        seg_num = i + 1
        segments.append(SourceSegment(
            source_id=source_id,
            segment_id=f"seg_{seg_num:06d}",
            page_start=_page_at(start),
            page_end=_page_at(end - 1),
            heading_path=heading_path,
            text=text,
            start_char=start,
            end_char=end,
        ))

    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING002PagePreservingParse tests/test_ingest_parse.py -v --no-header`
Expected: ALL PASSED (new tests + existing parse tests still green)

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/cli/ingest/parse.py tests/test_phase0_regression.py
git commit -m "fix(ING-002): implement true page-preserving parse with page markers"
```

---

### Task 3: ING-003 — Globally unique segment IDs with lineage

**Files:**
- Modify: `src/capability_commons/cli/ingest/parse.py:78-80`
- Modify: `src/capability_commons/cli/ingest/models.py:12-24`
- Modify: `src/capability_commons/cli/ingest/draft.py:96-101`
- Modify: `src/capability_commons/cli/ingest/cite.py:82-87`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test for globally unique segment IDs**

```python
class TestING003GlobalSegmentIDs:
    def test_segment_ids_include_source_prefix(self):
        """ING-003: segment IDs must be globally unique by including source_id."""
        md = "# A\nText A\n# B\nText B\n"
        segs_a = markdown_to_segments(md, source_id="src.alpha", base_page=1)
        segs_b = markdown_to_segments(md, source_id="src.beta", base_page=1)
        ids_a = {s.segment_id for s in segs_a}
        ids_b = {s.segment_id for s in segs_b}
        # No overlap between sources
        assert ids_a.isdisjoint(ids_b), f"Collision: {ids_a & ids_b}"

    def test_segment_ids_are_deterministic(self):
        """ING-003: same input produces same segment IDs."""
        md = "# Heading\nContent.\n"
        segs1 = markdown_to_segments(md, source_id="src.test", base_page=1)
        segs2 = markdown_to_segments(md, source_id="src.test", base_page=1)
        assert [s.segment_id for s in segs1] == [s.segment_id for s in segs2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING003GlobalSegmentIDs -v --no-header 2>&1 | head -15`
Expected: FAIL — current IDs are `seg_000001` regardless of source

- [ ] **Step 3: Update segment ID generation to include source_id**

In `src/capability_commons/cli/ingest/parse.py`, change the two places that generate segment IDs:

For the no-headings case:
```python
segment_id=f"{source_id}::seg_000001",
```

For the heading-split case:
```python
segment_id=f"{source_id}::seg_{seg_num:06d}",
```

- [ ] **Step 4: Add source_segment_ids field to DraftObject model**

In `src/capability_commons/cli/ingest/draft.py`, update the DraftObject class (line 96-101):

```python
class DraftObject(BaseModel, extra="allow"):
    id: str
    slug: str
    canonical_title: str
    markdown_body: str
    source_segment_ids: list[str] = []
```

And after generating the draft (line ~118), add segment IDs:

```python
result = await client.generate(...)
# Attach source segment lineage
result.source_segment_ids = [
    sid for sid in seg_ids if sid in segments_by_id
]
```

- [ ] **Step 5: Scope cite.py to object's source segments**

In `src/capability_commons/cli/ingest/cite.py`, change the segment selection logic (lines 82-87):

```python
# Scope to the object's source segments when available
source_seg_ids = set(obj.get("source_segment_ids", []))
if source_seg_ids:
    relevant_segs = [s for s in segments_by_id.values() if s.segment_id in source_seg_ids]
    # Add bounded neighbor context (segments adjacent in the same source)
    all_source_segs = sorted(
        [s for s in segments_by_id.values() if s.source_id == (obj.get("source_id") or "")],
        key=lambda s: s.start_char,
    )
    for seg in list(relevant_segs):
        idx = next((i for i, s in enumerate(all_source_segs) if s.segment_id == seg.segment_id), None)
        if idx is not None:
            for offset in [-1, 1]:
                ni = idx + offset
                if 0 <= ni < len(all_source_segs) and all_source_segs[ni].segment_id not in source_seg_ids:
                    relevant_segs.append(all_source_segs[ni])
else:
    # Fallback: all segments from the object's source
    source_id = obj.get("source_id") or (
        project.manifest.sources[0].id if project.manifest.sources else ""
    )
    relevant_segs = [s for s in segments_by_id.values() if s.source_id == source_id]
```

- [ ] **Step 6: Fix existing test that checks old segment ID format**

In `tests/test_ingest_parse.py`, update `test_assigns_sequential_ids`:

```python
def test_assigns_sequential_ids(self):
    md = "# A\nText A\n# B\nText B\n# C\nText C\n"
    segments = markdown_to_segments(md, source_id="src.test", base_page=1)
    ids = [s.segment_id for s in segments]
    assert ids == ["src.test::seg_000001", "src.test::seg_000002", "src.test::seg_000003"]
```

- [ ] **Step 7: Run all parse and regression tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py tests/test_ingest_parse.py -v --no-header`
Expected: ALL PASSED

- [ ] **Step 8: Commit**

```bash
git add src/capability_commons/cli/ingest/parse.py src/capability_commons/cli/ingest/draft.py src/capability_commons/cli/ingest/cite.py tests/test_phase0_regression.py tests/test_ingest_parse.py
git commit -m "fix(ING-003): globally unique segment IDs with source lineage in drafts"
```

---

### Task 4: ING-004 — Enforce full canonical draft schema

**Files:**
- Create: `src/capability_commons/cli/ingest/canonical_schema.py`
- Modify: `src/capability_commons/cli/ingest/draft.py:96-101`
- Modify: `src/capability_commons/cli/ingest/models.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test for canonical draft validation**

```python
class TestING004CanonicalDraftSchema:
    def test_valid_draft_passes(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        draft = CanonicalDraft(
            id="water.storage",
            slug="water.storage",
            co_type="skill_guide",
            canonical_title="Water Storage Basics",
            plain_language="Learn safe water storage.",
            markdown_body="# Water Storage\nStore water safely.",
            structured_data={"tools": ["container"]},
        )
        assert draft.slug == "water.storage"

    def test_missing_co_type_fails(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        with pytest.raises(Exception):
            CanonicalDraft(
                id="test",
                slug="test",
                canonical_title="Test",
                markdown_body="body",
            )

    def test_missing_plain_language_fails(self):
        from capability_commons.cli.ingest.canonical_schema import CanonicalDraft
        with pytest.raises(Exception):
            CanonicalDraft(
                id="test",
                slug="test",
                co_type="skill_guide",
                canonical_title="Test",
                markdown_body="body",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING004CanonicalDraftSchema -v --no-header 2>&1 | head -15`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create the canonical draft schema**

```python
# src/capability_commons/cli/ingest/canonical_schema.py
"""Canonical draft schema — the release gate for Pass 2 output."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, field_validator

VALID_CO_TYPES = {
    "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
    "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
    "field_report", "worksheet", "glossary", "safety_notice", "correction",
}


class CanonicalDraft(BaseModel, extra="allow"):
    """Full schema for a canonical draft object produced by Pass 2.

    This enforces the fields that downstream passes (cite, canonicalize,
    edges, load) depend on. The thin DraftObject model is replaced by this.
    """
    id: str
    slug: str
    co_type: str
    canonical_title: str
    plain_language: str
    markdown_body: str
    structured_data: dict[str, Any] = {}
    version_no: int = 1
    lifecycle_state: str = "draft"
    visibility: str = "public"
    language_code: str = "en"
    primary_domain: str = ""
    secondary_domains: list[str] = []
    stage: str = ""
    contexts: list[str] = []
    difficulty: int | None = None
    cost_band: str = "free"
    risk_band: str = "low"
    summary_short: str = ""
    summary_medium: str = ""
    requires: list = []
    suggested_edges: list = []
    citations: list = []
    source_segment_ids: list[str] = []

    @field_validator("co_type")
    @classmethod
    def validate_co_type(cls, v: str) -> str:
        normalized = v.lower().replace(" ", "_")
        if normalized not in VALID_CO_TYPES:
            raise ValueError(f"Invalid co_type: {v}")
        return normalized
```

- [ ] **Step 4: Update draft.py to use CanonicalDraft as the response model**

In `src/capability_commons/cli/ingest/draft.py`, replace the DraftObject class and usage:

```python
from capability_commons.cli.ingest.canonical_schema import CanonicalDraft

# Remove the old DraftObject class definition entirely

# In the generation loop, change response_model:
result = await client.generate(
    system=SYSTEM_PROMPT,
    user=user_msg,
    response_model=CanonicalDraft,
)
# Attach source segment lineage
result.source_segment_ids = [
    sid for sid in seg_ids if sid in segments_by_id
]
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING004CanonicalDraftSchema -v --no-header`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/cli/ingest/canonical_schema.py src/capability_commons/cli/ingest/draft.py tests/test_phase0_regression.py
git commit -m "feat(ING-004): enforce full canonical draft schema in Pass 2"
```

---

### Task 5: ING-005 — Materialize merge/split decisions in canonicalization

**Files:**
- Modify: `src/capability_commons/cli/ingest/canonicalize.py:127-155`
- Modify: `src/capability_commons/cli/ingest/models.py:82-88`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

```python
class TestING005CanonicalizationMaterialization:
    def test_merge_decision_schema_includes_merged_object(self):
        """ING-005: CanonicalizationDecision for merge must include merged_object."""
        from capability_commons.cli.ingest.models import CanonicalizationDecision
        d = CanonicalizationDecision(
            action="merge",
            rationale="duplicates",
            canonical_slug="water.storage",
            deprecated_draft_ids=["water.storage-v1", "water.storage-v2"],
            merged_object={"id": "water.storage", "slug": "water.storage", "co_type": "skill_guide",
                           "canonical_title": "Water Storage", "plain_language": "Store water.",
                           "markdown_body": "# Water Storage"},
        )
        assert d.merged_object is not None
        assert d.merged_object["slug"] == "water.storage"

    def test_split_decision_schema_includes_split_objects(self):
        """ING-005: CanonicalizationDecision for split must include split_objects."""
        from capability_commons.cli.ingest.models import CanonicalizationDecision
        d = CanonicalizationDecision(
            action="split",
            rationale="overloaded",
            canonical_slug="water.storage",
            deprecated_draft_ids=["water.combined"],
            split_objects=[
                {"id": "water.storage", "slug": "water.storage", "co_type": "skill_guide",
                 "canonical_title": "Storage", "plain_language": "Store.", "markdown_body": "body"},
                {"id": "water.treatment", "slug": "water.treatment", "co_type": "skill_guide",
                 "canonical_title": "Treatment", "plain_language": "Treat.", "markdown_body": "body"},
            ],
        )
        assert len(d.split_objects) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING005CanonicalizationMaterialization -v --no-header 2>&1 | head -15`
Expected: FAIL — merged_object/split_objects fields don't exist

- [ ] **Step 3: Extend CanonicalizationDecision model**

In `src/capability_commons/cli/ingest/models.py`, update:

```python
class CanonicalizationDecision(BaseModel):
    """A merge/split/keep decision for a group of similar drafts."""
    action: Literal["keep", "merge", "split"]
    rationale: str
    canonical_slug: str
    deprecated_draft_ids: list[str] = []
    merged_object: dict | None = None
    split_objects: list[dict] = []
```

- [ ] **Step 4: Update canonicalize.py to write materialized objects**

In `src/capability_commons/cli/ingest/canonicalize.py`, after the merge/split decisions (lines ~133-155):

```python
if decision.action == "merge":
    for dep_id in decision.deprecated_draft_ids:
        src = project.drafts_dir / f"{dep_id}.yaml"
        if src.exists():
            shutil.move(str(src), str(merged_dir / src.name))
    # Write the merged replacement object
    if decision.merged_object:
        merged_path = project.drafts_dir / f"{decision.canonical_slug}.yaml"
        with open(merged_path, "w") as f:
            yaml.dump(decision.merged_object, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    console.print(
        f"    [green]merge[/green] -> {decision.canonical_slug} "
        f"(deprecated: {decision.deprecated_draft_ids})"
    )
elif decision.action == "split":
    for dep_id in decision.deprecated_draft_ids:
        src = project.drafts_dir / f"{dep_id}.yaml"
        if src.exists():
            shutil.move(str(src), str(split_dir / src.name))
    # Write split child objects
    for child in decision.split_objects:
        child_slug = child.get("slug") or child.get("id", "")
        if child_slug:
            child_path = project.drafts_dir / f"{child_slug}.yaml"
            with open(child_path, "w") as f:
                yaml.dump(child, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    console.print(
        f"    [blue]split[/blue] {decision.canonical_slug} -> "
        f"{[c.get('slug', '') for c in decision.split_objects]} "
        f"(original: {decision.deprecated_draft_ids})"
    )
```

Also update the LLM prompt in `USER_TEMPLATE` to request the merged/split objects:

```python
USER_TEMPLATE = """These drafts appear similar. For each group, decide:
- "keep": both are distinct, no changes needed
- "merge": combine into one canonical object. Include the full merged object as "merged_object".
- "split": one object should be split into multiple. Include the split objects as "split_objects".

Return a JSON object with key "decisions" containing an array of decisions.
Each decision: {{action, rationale, canonical_slug, deprecated_draft_ids, merged_object (if merge), split_objects (if split)}}

Draft set:
{drafts}"""
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestING005CanonicalizationMaterialization -v --no-header`
Expected: ALL PASSED

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/cli/ingest/models.py src/capability_commons/cli/ingest/canonicalize.py tests/test_phase0_regression.py
git commit -m "feat(ING-005): materialize merge/split decisions in canonicalization"
```

---

### Task 6: SEED-001 — Normalize edge-type imports

**Files:**
- Modify: `src/capability_commons/cli/seed.py:58-65,306-343`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

```python
class TestSEED001EdgeTypeNormalization:
    def test_normalize_edge_type_accepts_lowercase_enum(self):
        """SEED-001: normalizer must accept canonical lowercase enum values."""
        from capability_commons.cli.seed import normalize_edge_type
        from capability_commons.domain.enums import EdgeType
        assert normalize_edge_type("prerequisite_for") == EdgeType.PREREQUISITE_FOR
        assert normalize_edge_type("builds_on") == EdgeType.BUILDS_ON
        assert normalize_edge_type("contains") == EdgeType.CONTAINS

    def test_normalize_edge_type_accepts_legacy_uppercase(self):
        """SEED-001: normalizer must accept legacy CSV uppercase names."""
        from capability_commons.cli.seed import normalize_edge_type
        from capability_commons.domain.enums import EdgeType
        assert normalize_edge_type("REQUIRES") == EdgeType.PREREQUISITE_FOR
        assert normalize_edge_type("NEXT") == EdgeType.NEXT_STEP_FOR
        assert normalize_edge_type("COVERS") == EdgeType.CONTAINS

    def test_normalize_edge_type_unknown_returns_none(self):
        """SEED-001: unknown edge types return None."""
        from capability_commons.cli.seed import normalize_edge_type
        assert normalize_edge_type("NONEXISTENT") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestSEED001EdgeTypeNormalization -v --no-header 2>&1 | head -15`
Expected: FAIL — `normalize_edge_type` doesn't exist

- [ ] **Step 3: Add normalize_edge_type helper and use it**

In `src/capability_commons/cli/seed.py`, add after the existing maps (around line 88):

```python
def normalize_edge_type(raw: str) -> EdgeType | None:
    """Normalize an edge type string to an EdgeType enum value.

    Accepts:
    - Canonical lowercase enum values: 'prerequisite_for', 'builds_on', etc.
    - Legacy uppercase CSV names: 'REQUIRES', 'NEXT', 'COVERS', etc.
    """
    # Try legacy seed mapping first
    if raw in SEED_EDGE_TO_EDGE_TYPE:
        return SEED_EDGE_TO_EDGE_TYPE[raw]
    # Try canonical enum value (lowercase)
    try:
        return EdgeType(raw.lower())
    except ValueError:
        pass
    # Try uppercase -> lowercase
    try:
        return EdgeType(raw.lower())
    except ValueError:
        return None
```

Update the suggested_edges loader (lines ~320-321) to use normalize_edge_type:

```python
et = normalize_edge_type(edge_type_str)
if et is None:
    print(f"  WARN: unknown edge type {edge_type_str}")
    continue
```

Update the CSV edges loader (lines ~402-403) to use normalize_edge_type:

```python
edge_type = normalize_edge_type(seed_type)
if edge_type is None:
    print(f"  WARN: unknown edge type {seed_type}, skipping")
    continue
```

- [ ] **Step 4: Run all seed tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestSEED001EdgeTypeNormalization tests/test_seed.py -v --no-header`
Expected: ALL PASSED

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/cli/seed.py tests/test_phase0_regression.py
git commit -m "fix(SEED-001): normalize edge-type imports to handle both legacy and canonical names"
```

---

### Task 7: SEED-002 — Add metadata_json to EvidenceSpan

**Files:**
- Modify: `src/capability_commons/db/models.py:298-318`
- Create: `alembic/versions/20260329_0001_evidence_span_metadata.py`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

```python
class TestSEED002EvidenceSpanMetadata:
    def test_evidence_span_model_has_metadata_json(self):
        """SEED-002: EvidenceSpan ORM model must have metadata_json column."""
        from capability_commons.db.models import EvidenceSpan
        assert hasattr(EvidenceSpan, "metadata_json")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestSEED002EvidenceSpanMetadata -v --no-header 2>&1 | head -10`
Expected: FAIL — EvidenceSpan doesn't have metadata_json

- [ ] **Step 3: Add metadata_json column to EvidenceSpan model**

In `src/capability_commons/db/models.py`, add to the EvidenceSpan class (after `checksum` on line 312):

```python
metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
```

- [ ] **Step 4: Create Alembic migration**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m alembic revision --autogenerate -m "add metadata_json to evidence_spans"`

If autogenerate doesn't work due to DB connection, create manually:

```python
# alembic/versions/20260329_0001_evidence_span_metadata.py
"""Add metadata_json to evidence_spans.

Revision ID: 20260329_0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260329_0001"
down_revision = None  # Will be set to the latest existing revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence_spans",
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("evidence_spans", "metadata")
```

- [ ] **Step 5: Run test**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestSEED002EvidenceSpanMetadata -v --no-header`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/db/models.py alembic/versions/20260329_0001_evidence_span_metadata.py tests/test_phase0_regression.py
git commit -m "feat(SEED-002): add metadata_json column to EvidenceSpan for citation provenance"
```

---

### Task 8: PUB-001 — Make ingest-loaded published content trigger indexing

**Files:**
- Modify: `src/capability_commons/cli/seed.py:246-248`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

```python
class TestPUB001PublishIndexing:
    def test_seed_graph_emits_outbox_event(self):
        """PUB-001: seed_graph must emit version.published outbox events."""
        # We test that the seed_graph code path includes outbox event creation
        # by checking that the helper is imported and called
        import ast
        import inspect
        from capability_commons.cli import seed
        source = inspect.getsource(seed.seed_graph)
        tree = ast.parse(source)
        # Check for add_outbox_event call in the AST
        has_outbox = any(
            isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id == "add_outbox_event") or
                (isinstance(node.func, ast.Attribute) and node.func.attr == "add_outbox_event")
            )
            for node in ast.walk(tree)
        )
        assert has_outbox, "seed_graph must call add_outbox_event for published versions"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestPUB001PublishIndexing -v --no-header 2>&1 | head -10`
Expected: FAIL — seed_graph doesn't call add_outbox_event

- [ ] **Step 3: Add outbox event emission to seed_graph**

In `src/capability_commons/cli/seed.py`, add import at top:

```python
from capability_commons.services.helpers import add_outbox_event
```

After `obj.published_at = obj.created_at` (line ~248), add:

```python
# Emit publish event so the worker indexes/embeds this version
await add_outbox_event(
    session,
    aggregate_type="context_object",
    aggregate_id=obj.id,
    event_type="version.published",
    payload={"object_id": str(obj.id), "version_id": str(version.id)},
)
```

- [ ] **Step 4: Run test**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestPUB001PublishIndexing -v --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/cli/seed.py tests/test_phase0_regression.py
git commit -m "fix(PUB-001): emit outbox events from seed_graph so published content gets indexed"
```

---

### Task 9: API-SEC-001 — Protect retrieval run detail endpoints

**Files:**
- Modify: `src/capability_commons/api/routes/retrieval.py:30-39`
- Test: `tests/test_phase0_regression.py`

- [ ] **Step 1: Write the failing test**

```python
class TestAPISEC001RetrievalRunAccess:
    def test_get_run_requires_workspace(self):
        """API-SEC-001: retrieval run detail endpoints must require workspace auth."""
        import inspect
        from capability_commons.api.routes import retrieval
        source = inspect.getsource(retrieval.get_run)
        # The function signature must include workspace parameter
        sig = inspect.signature(retrieval.get_run)
        param_annotations = {
            name: str(p.annotation) for name, p in sig.parameters.items()
        }
        has_workspace = any("CurrentWorkspace" in str(ann) for ann in param_annotations.values())
        assert has_workspace, "get_run must require CurrentWorkspace dependency"

    def test_get_steps_requires_workspace(self):
        """API-SEC-001: retrieval run steps endpoint must require workspace auth."""
        import inspect
        from capability_commons.api.routes import retrieval
        sig = inspect.signature(retrieval.get_run_steps)
        param_annotations = {
            name: str(p.annotation) for name, p in sig.parameters.items()
        }
        has_workspace = any("CurrentWorkspace" in str(ann) for ann in param_annotations.values())
        assert has_workspace, "get_run_steps must require CurrentWorkspace dependency"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestAPISEC001RetrievalRunAccess -v --no-header 2>&1 | head -15`
Expected: FAIL — endpoints don't have CurrentWorkspace parameter

- [ ] **Step 3: Add workspace auth to retrieval run endpoints**

In `src/capability_commons/api/routes/retrieval.py`, update the two endpoints:

```python
@router.get("/retrieval_runs/{run_id}", response_model=RetrievalRunResponse)
async def get_run(
    run_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> RetrievalRunResponse:
    service = RetrievalService(session)
    return await service.get_run(run_id, workspace_id=workspace.id)


@router.get("/retrieval_runs/{run_id}/steps", response_model=list[RetrievalStepResponse])
async def get_run_steps(
    run_id: uuid.UUID,
    session: DBSession,
    workspace: CurrentWorkspace,
) -> list[RetrievalStepResponse]:
    service = RetrievalService(session)
    return await service.get_steps(run_id, workspace_id=workspace.id)
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/test_phase0_regression.py::TestAPISEC001RetrievalRunAccess -v --no-header`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/api/routes/retrieval.py tests/test_phase0_regression.py
git commit -m "fix(API-SEC-001): protect retrieval run detail endpoints with workspace auth"
```

---

### Task 10: Run full test suite and final commit

- [ ] **Step 1: Run the entire test suite**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python -m pytest tests/ -v --no-header -x 2>&1 | tail -40`
Expected: All tests pass (or only pre-existing failures unrelated to our changes)

- [ ] **Step 2: Fix any regressions**

If tests fail, diagnose and fix. The most likely issues are:
- Old tests checking for uppercase lifecycle values
- Old tests checking for `seg_NNNNNN` format without source prefix

- [ ] **Step 3: Final commit if any additional fixes were needed**

```bash
git add -u
git commit -m "fix: resolve test regressions from Phase 0 correctness fixes"
```
