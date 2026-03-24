# Ingestion Tooling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-pass CLI pipeline (`python -m capability_commons.cli.ingest`) that converts source PDFs into fully populated Capability Commons knowledge objects with body text, citations, edges, and bundles.

**Architecture:** Flat CLI modules under `src/capability_commons/cli/ingest/`, one file per pipeline pass. A shared LLM client wraps the OpenAI-compatible API with Pydantic validation + retry. Intermediate artifacts live in `ingestion/projects/<name>/` as JSONL, CSV, and YAML files. The `load` step extends the existing `seed.py` to handle richer YAML with citations and evidence spans.

**Tech Stack:** Python 3.11+, marker-pdf, openai SDK, polars, orjson, rich, aiofiles, tiktoken, rapidfuzz, Pydantic 2, SQLAlchemy 2 async, Alembic, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-23-ingestion-tooling-design.md`

---

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `src/capability_commons/cli/ingest/__init__.py` | Package marker |
| `src/capability_commons/cli/ingest/__main__.py` | Argparse dispatch for all commands |
| `src/capability_commons/cli/ingest/models.py` | Pydantic models for all intermediate artifacts |
| `src/capability_commons/cli/ingest/project.py` | Project directory management + manifest I/O |
| `src/capability_commons/cli/ingest/llm_client.py` | OpenAI-compatible client with Pydantic retry |
| `src/capability_commons/cli/ingest/parse.py` | Pass 0: PDF → markdown segments |
| `src/capability_commons/cli/ingest/extract.py` | Pass 1: segments → extraction matrix |
| `src/capability_commons/cli/ingest/draft.py` | Pass 2: matrix → canonical YAML objects |
| `src/capability_commons/cli/ingest/cite.py` | Pass 3: drafts → citation linking |
| `src/capability_commons/cli/ingest/canonicalize.py` | Pass 4: dedup, merge, split |
| `src/capability_commons/cli/ingest/edges.py` | Pass 5: object set → edges CSV |
| `src/capability_commons/cli/ingest/bundles.py` | Pass 6: objects → six-part bundles |
| `src/capability_commons/cli/ingest/load.py` | Pass 7: validate + load to database |
| `tests/test_ingest_models.py` | Unit tests for Pydantic models |
| `tests/test_ingest_project.py` | Unit tests for project directory management |
| `tests/test_ingest_llm_client.py` | Unit tests for LLM client with mocked HTTP |
| `tests/test_ingest_parse.py` | Integration test for PDF parsing |
| `tests/test_ingest_load.py` | Integration test for rich YAML loading |
| `tests/test_ingest_passes.py` | Unit tests for LLM passes with mocked responses |
| `tests/fixtures/ingest/` | Test fixture files (small PDF, sample YAML, mocked LLM responses) |
| `alembic/versions/20260323_0001_evidence_external_id.py` | Migration: add `external_id` to `evidence_sources` |

### Existing files to modify

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `[ingest]` optional dependency group |
| `src/capability_commons/cli/seed.py` | Handle richer YAML fields, both `requires` formats, `co_type`, citations, suggested_edges |
| `src/capability_commons/db/models.py` | Add `external_id` column to `EvidenceSource` |
| `ingestion/README.md` | Rewrite as practical operator guide |

---

## Chunk 1: Foundation

### Task 1: Add `[ingest]` optional dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml:28-34`

- [ ] **Step 1: Add the ingest dependency group**

After the existing `dev` group in `pyproject.toml`, add:

```toml
ingest = [
  "marker-pdf>=1.0,<2.0",
  "openai>=1.0,<2.0",
  "polars>=1.0",
  "orjson>=3.9,<4.0",
  "rich>=13.0,<14.0",
  "aiofiles>=24.0,<25.0",
  "tiktoken>=0.7",
  "rapidfuzz>=3.0",
]
```

- [ ] **Step 2: Verify installation**

Run: `cd ~/Projects/CapabilityCommons && pip install -e ".[ingest]"`
Expected: All packages install without errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add [ingest] optional dependency group"
```

---

### Task 2: Create Pydantic models for intermediate artifacts

**Files:**
- Create: `src/capability_commons/cli/ingest/__init__.py`
- Create: `src/capability_commons/cli/ingest/models.py`
- Create: `tests/test_ingest_models.py`

- [ ] **Step 1: Create the package**

Create `src/capability_commons/cli/ingest/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests for all models**

Create `tests/test_ingest_models.py`:

```python
"""Tests for ingestion pipeline Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_commons.cli.ingest.models import (
    CanonicalizationDecision,
    CitationSpan,
    ClaimCitation,
    ExtractedEdge,
    ExtractionRow,
    ManifestSource,
    ProjectManifest,
    SourceSegment,
    ValidationReport,
)


class TestSourceSegment:
    def test_valid_segment(self):
        seg = SourceSegment(
            source_id="src.test.book",
            segment_id="seg_000001",
            page_start=1,
            page_end=1,
            heading_path=["Chapter 1", "Section A"],
            text="Some content here.",
            start_char=0,
            end_char=18,
        )
        assert seg.segment_id == "seg_000001"
        assert seg.figure_refs == []
        assert seg.table_refs == []

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SourceSegment(
                source_id="src.test",
                segment_id="seg_000001",
                page_start=1,
                page_end=1,
                heading_path=[],
                # text is missing
                start_char=0,
                end_char=0,
            )


class TestExtractionRow:
    def test_valid_row(self):
        row = ExtractionRow(
            source_id="src.test",
            section_id="sec_001",
            start_page=1,
            end_page=3,
            heading_path="Chapter 1 > Section A",
            segment_ids=["seg_001", "seg_002"],
            candidate_slug="water.storage-basics",
            candidate_type="skill_guide",
            primary_domain="water",
            stage="household",
            summary="How to store water safely.",
            confidence=0.91,
        )
        assert row.candidate_type == "skill_guide"
        assert row.needs_split is False

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ExtractionRow(
                source_id="src.test",
                section_id="sec_001",
                start_page=1,
                end_page=1,
                heading_path="Ch1",
                segment_ids=[],
                candidate_slug="x.y",
                candidate_type="invalid_type",
                primary_domain="water",
                stage="household",
                summary="Test",
                confidence=0.5,
            )


class TestCitationSpan:
    def test_valid_span(self):
        span = CitationSpan(
            source_id="src.test",
            page_start=10,
            page_end=10,
            segment_id="seg_010",
            excerpt="water should be stored",
            start_char=50,
            end_char=72,
            support_strength="strong",
        )
        assert span.support_strength == "strong"

    def test_invalid_strength(self):
        with pytest.raises(ValidationError):
            CitationSpan(
                source_id="src.test",
                page_start=1,
                page_end=1,
                segment_id="seg_001",
                excerpt="test",
                start_char=0,
                end_char=4,
                support_strength="very_strong",
            )


class TestClaimCitation:
    def test_valid_citation(self):
        cc = ClaimCitation(
            object_id="water.storage-basics",
            claim_id="clm_001",
            claim_text="Water should be stored in food-grade containers.",
            support=[
                CitationSpan(
                    source_id="src.test",
                    page_start=10,
                    page_end=10,
                    segment_id="seg_010",
                    excerpt="food-grade containers",
                    start_char=50,
                    end_char=71,
                    support_strength="strong",
                )
            ],
        )
        assert len(cc.support) == 1


class TestExtractedEdge:
    def test_valid_edge(self):
        edge = ExtractedEdge(
            source_id="water.storage-basics",
            target_id="water.treatment-selection",
            edge_type="prerequisite_for",
            confidence=0.85,
        )
        assert edge.sequence is None
        assert edge.condition is None

    def test_with_optional_fields(self):
        edge = ExtractedEdge(
            source_id="a",
            target_id="b",
            edge_type="next_step_for",
            sequence=1,
            condition="after storage is set up",
            confidence=0.77,
        )
        assert edge.sequence == 1


class TestCanonicalizationDecision:
    def test_merge(self):
        d = CanonicalizationDecision(
            action="merge",
            rationale="Same learner outcome.",
            canonical_slug="water.storage-basics",
            deprecated_draft_ids=["water.water-store", "water.storing-water"],
        )
        assert d.action == "merge"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            CanonicalizationDecision(
                action="delete",
                rationale="test",
                canonical_slug="x",
            )


class TestValidationReport:
    def test_valid_report(self):
        r = ValidationReport(
            objects_count=10,
            edges_count=25,
            citations_count=8,
            errors=[],
            warnings=["Object food.seed-x has no citations"],
            citation_coverage=0.80,
        )
        assert r.citation_coverage == 0.80


class TestProjectManifest:
    def test_valid_manifest(self):
        m = ProjectManifest(
            name="test-project",
            created="2026-03-23T12:00:00Z",
            sources=[
                ManifestSource(
                    id="src.test",
                    file="sources/test.pdf",
                    title="Test Book",
                    source_kind="BOOK",
                )
            ],
        )
        assert m.name == "test-project"
        assert m.passes.parse.completed is None

    def test_default_passes(self):
        m = ProjectManifest(
            name="test",
            created="2026-03-23T00:00:00Z",
            sources=[],
        )
        assert m.passes.extract.completed is None
        assert m.passes.load.completed is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capability_commons.cli.ingest.models'`

- [ ] **Step 4: Implement all models**

Create `src/capability_commons/cli/ingest/models.py`:

```python
"""Pydantic models for ingestion pipeline intermediate artifacts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# --- Pass 0: Segments ---

class SourceSegment(BaseModel):
    """A page-preserving text segment extracted from a source document."""
    source_id: str
    segment_id: str
    page_start: int
    page_end: int
    heading_path: list[str]
    text: str
    start_char: int
    end_char: int
    figure_refs: list[str] = []
    table_refs: list[str] = []


# --- Pass 1: Extraction Matrix ---

class ExtractionRow(BaseModel):
    """A candidate capability object identified from source material."""
    source_id: str
    section_id: str
    start_page: int
    end_page: int
    heading_path: str
    segment_ids: list[str]
    candidate_slug: str
    candidate_type: Literal[
        "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
        "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
        "field_report", "worksheet", "glossary", "safety_notice", "correction",
    ]
    primary_domain: str
    secondary_domains: list[str] = []
    stage: str
    contexts: list[str] = []
    summary: str
    key_concepts: list[str] = []
    key_actions: list[str] = []
    tools_materials: list[str] = []
    failure_modes: list[str] = []
    safety_boundaries: list[str] = []
    local_adaptation_signals: list[str] = []
    needs_split: bool = False
    needs_merge: bool = False
    confidence: float


# --- Pass 3: Citations ---

class CitationSpan(BaseModel):
    """A link from a claim to a source text span."""
    source_id: str
    page_start: int
    page_end: int
    segment_id: str
    excerpt: str
    start_char: int
    end_char: int
    support_strength: Literal["strong", "medium", "weak"]


class ClaimCitation(BaseModel):
    """A drafted claim linked to supporting source spans."""
    object_id: str
    claim_id: str
    claim_text: str
    support: list[CitationSpan]


# --- Pass 4: Canonicalization ---

class CanonicalizationDecision(BaseModel):
    """A merge/split/keep decision for a group of similar drafts."""
    action: Literal["keep", "merge", "split"]
    rationale: str
    canonical_slug: str
    deprecated_draft_ids: list[str] = []


# --- Pass 5: Edges ---

class ExtractedEdge(BaseModel):
    """A typed directed edge between two knowledge objects."""
    source_id: str
    target_id: str
    edge_type: str
    sequence: int | None = None
    condition: str | None = None
    confidence: float


# --- Pass 6: Bundles ---

class BundleOutput(BaseModel):
    """Six-part public bundle for a knowledge object."""
    hook: str
    primer: str
    guide: str
    reference: list[str]
    worksheet: list[str]
    teach_forward_kit: dict[str, str | list[str]]


# --- Validation ---

class ValidationReport(BaseModel):
    """Summary report from the validate command."""
    objects_count: int
    edges_count: int
    citations_count: int
    errors: list[str]
    warnings: list[str]
    citation_coverage: float


# --- Project Manifest ---

class PassStatus(BaseModel):
    """Completion status for a single pipeline pass."""
    completed: datetime | None = None


class PassesStatus(BaseModel):
    """Completion status for all pipeline passes."""
    parse: PassStatus = PassStatus()
    extract: PassStatus = PassStatus()
    draft: PassStatus = PassStatus()
    cite: PassStatus = PassStatus()
    canonicalize: PassStatus = PassStatus()
    edges: PassStatus = PassStatus()
    bundles: PassStatus = PassStatus()
    load: PassStatus = PassStatus()


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.2


class ManifestSource(BaseModel):
    """A source document registered in the project."""
    id: str
    file: str
    title: str
    source_kind: str


class ProjectManifest(BaseModel):
    """Top-level manifest for an ingestion project."""
    name: str
    created: str
    sources: list[ManifestSource]
    llm: LLMConfig = LLMConfig()
    passes: PassesStatus = PassesStatus()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_models.py -v`
Expected: All 14 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/cli/ingest/__init__.py \
        src/capability_commons/cli/ingest/models.py \
        tests/test_ingest_models.py
git commit -m "feat(ingest): add Pydantic models for pipeline artifacts"
```

---

### Task 3: Create project directory management

**Files:**
- Create: `src/capability_commons/cli/ingest/project.py`
- Create: `tests/test_ingest_project.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ingest_project.py`:

```python
"""Tests for ingestion project directory management."""
from __future__ import annotations

import pytest
import yaml

from capability_commons.cli.ingest.project import IngestProject


@pytest.fixture
def projects_root(tmp_path):
    """Return a temporary projects root directory."""
    return tmp_path / "projects"


class TestIngestProjectInit:
    def test_init_creates_directory_structure(self, projects_root):
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test-project",
            sources=[{
                "id": "src.test",
                "file": "/tmp/test.pdf",
                "title": "Test Book",
                "source_kind": "BOOK",
            }],
        )
        assert (proj.root / "manifest.yaml").exists()
        assert (proj.root / "sources").is_dir()
        assert (proj.root / "segments").is_dir()
        assert (proj.root / "matrix").is_dir()
        assert (proj.root / "drafts").is_dir()
        assert (proj.root / "citations").is_dir()
        assert (proj.root / "edges").is_dir()
        assert (proj.root / "output").is_dir()
        assert (proj.root / "logs").is_dir()

    def test_manifest_is_valid_yaml(self, projects_root):
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test-project",
            sources=[{
                "id": "src.test",
                "file": "/tmp/test.pdf",
                "title": "Test Book",
                "source_kind": "BOOK",
            }],
        )
        manifest = yaml.safe_load((proj.root / "manifest.yaml").read_text())
        assert manifest["name"] == "test-project"
        assert len(manifest["sources"]) == 1
        assert manifest["sources"][0]["id"] == "src.test"

    def test_init_rejects_existing_project(self, projects_root):
        IngestProject.init(
            projects_root=projects_root,
            name="existing",
            sources=[],
        )
        with pytest.raises(FileExistsError):
            IngestProject.init(
                projects_root=projects_root,
                name="existing",
                sources=[],
            )


class TestIngestProjectLoad:
    def test_load_existing(self, projects_root):
        IngestProject.init(
            projects_root=projects_root,
            name="my-project",
            sources=[],
        )
        proj = IngestProject.load(projects_root, "my-project")
        assert proj.manifest.name == "my-project"

    def test_load_nonexistent_raises(self, projects_root):
        with pytest.raises(FileNotFoundError):
            IngestProject.load(projects_root, "nonexistent")


class TestIngestProjectPaths:
    def test_path_helpers(self, projects_root):
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test",
            sources=[],
        )
        assert proj.segments_dir == proj.root / "segments"
        assert proj.matrix_dir == proj.root / "matrix"
        assert proj.drafts_dir == proj.root / "drafts"
        assert proj.citations_dir == proj.root / "citations"
        assert proj.edges_dir == proj.root / "edges"
        assert proj.output_dir == proj.root / "output"
        assert proj.logs_dir == proj.root / "logs"
        assert proj.segments_file == proj.root / "segments" / "segments.jsonl"
        assert proj.matrix_file == proj.root / "matrix" / "extraction_matrix.csv"
        assert proj.evidence_map_file == proj.root / "citations" / "evidence_map.json"
        assert proj.edges_file == proj.root / "edges" / "edges.csv"


class TestIngestProjectPassTracking:
    def test_mark_pass_complete(self, projects_root):
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test",
            sources=[],
        )
        assert proj.manifest.passes.parse.completed is None
        proj.mark_pass_complete("parse")
        # Reload from disk
        proj2 = IngestProject.load(projects_root, "test")
        assert proj2.manifest.passes.parse.completed is not None

    def test_mark_invalid_pass_raises(self, projects_root):
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test",
            sources=[],
        )
        with pytest.raises(ValueError):
            proj.mark_pass_complete("nonexistent_pass")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_project.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement project management**

Create `src/capability_commons/cli/ingest/project.py`:

```python
"""Ingestion project directory management and manifest I/O."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from capability_commons.cli.ingest.models import (
    LLMConfig,
    ManifestSource,
    ProjectManifest,
)

SUBDIRS = [
    "sources", "segments", "matrix", "drafts", "citations",
    "edges", "output", "output/canonical/nodes", "output/imports", "logs",
]


class IngestProject:
    """Manages an ingestion project directory and its manifest."""

    def __init__(self, root: Path, manifest: ProjectManifest) -> None:
        self.root = root
        self.manifest = manifest

    # --- Constructors ---

    @classmethod
    def init(
        cls,
        projects_root: Path,
        name: str,
        sources: list[dict],
        llm_config: LLMConfig | None = None,
    ) -> IngestProject:
        """Create a new project directory with manifest."""
        project_dir = projects_root / name
        if project_dir.exists():
            raise FileExistsError(f"Project already exists: {project_dir}")

        project_dir.mkdir(parents=True)
        for subdir in SUBDIRS:
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)

        manifest = ProjectManifest(
            name=name,
            created=datetime.now(timezone.utc).isoformat(),
            sources=[ManifestSource(**s) for s in sources],
            llm=llm_config or LLMConfig(),
        )
        cls._write_manifest(project_dir, manifest)
        return cls(project_dir, manifest)

    @classmethod
    def load(cls, projects_root: Path, name: str) -> IngestProject:
        """Load an existing project from disk."""
        project_dir = projects_root / name
        manifest_path = project_dir / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Project not found: {project_dir}")

        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        manifest = ProjectManifest(**data)
        return cls(project_dir, manifest)

    # --- Path helpers ---

    @property
    def segments_dir(self) -> Path:
        return self.root / "segments"

    @property
    def matrix_dir(self) -> Path:
        return self.root / "matrix"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    @property
    def citations_dir(self) -> Path:
        return self.root / "citations"

    @property
    def edges_dir(self) -> Path:
        return self.root / "edges"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def segments_file(self) -> Path:
        return self.segments_dir / "segments.jsonl"

    @property
    def matrix_file(self) -> Path:
        return self.matrix_dir / "extraction_matrix.csv"

    @property
    def evidence_map_file(self) -> Path:
        return self.citations_dir / "evidence_map.json"

    @property
    def edges_file(self) -> Path:
        return self.edges_dir / "edges.csv"

    # --- Pass tracking ---

    def mark_pass_complete(self, pass_name: str) -> None:
        """Record that a pass has completed and save to manifest."""
        passes = self.manifest.passes
        if not hasattr(passes, pass_name):
            raise ValueError(f"Unknown pass: {pass_name}")
        getattr(passes, pass_name).completed = datetime.now(timezone.utc)
        self._write_manifest(self.root, self.manifest)

    def save_manifest(self) -> None:
        """Write current manifest state to disk."""
        self._write_manifest(self.root, self.manifest)

    @staticmethod
    def _write_manifest(project_dir: Path, manifest: ProjectManifest) -> None:
        """Serialize manifest to YAML on disk."""
        with open(project_dir / "manifest.yaml", "w") as f:
            yaml.dump(
                manifest.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_project.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/cli/ingest/project.py \
        tests/test_ingest_project.py
git commit -m "feat(ingest): add project directory management and manifest I/O"
```

---

### Task 4: Create LLM client with Pydantic retry

**Files:**
- Create: `src/capability_commons/cli/ingest/llm_client.py`
- Create: `tests/test_ingest_llm_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ingest_llm_client.py`:

```python
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
        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
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
        with patch.object(
            client._client.chat.completions,
            "create",
            side_effect=[bad_response, good_response],
        ):
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
        with patch.object(
            client._client.chat.completions,
            "create",
            return_value=bad_response,
        ):
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement LLM client**

Create `src/capability_commons/cli/ingest/llm_client.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_llm_client.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/cli/ingest/llm_client.py \
        tests/test_ingest_llm_client.py
git commit -m "feat(ingest): add LLM client with Pydantic validation and retry"
```

---

## Chunk 2: Database & Deterministic Passes

### Task 5: Alembic migration — add `external_id` to `evidence_sources`

**Files:**
- Create: `alembic/versions/20260323_0001_evidence_external_id.py`
- Modify: `src/capability_commons/db/models.py:277-294`

- [ ] **Step 1: Create the migration**

Create `alembic/versions/20260323_0001_evidence_external_id.py`:

```python
"""Add external_id to evidence_sources for ingestion pipeline.

Revision ID: 20260323_0001
Revises: 20260317_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260323_0001"
down_revision = "20260317_0001"


def upgrade() -> None:
    op.add_column(
        "evidence_sources",
        sa.Column("external_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_evidence_sources_external_id",
        "evidence_sources",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_sources_external_id", "evidence_sources")
    op.drop_column("evidence_sources", "external_id")
```

- [ ] **Step 2: Add `external_id` to the ORM model**

In `src/capability_commons/db/models.py`, add after line 288 (`language_code`):

```python
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
```

Also add `String` to the imports from `sqlalchemy` if not already present.

- [ ] **Step 3: Verify migration applies**

Run: `cd ~/Projects/CapabilityCommons && docker compose exec api alembic upgrade head`
Expected: Migration applies without errors.

If running locally: `alembic upgrade head`

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/20260323_0001_evidence_external_id.py \
        src/capability_commons/db/models.py
git commit -m "feat: add external_id column to evidence_sources for ingestion"
```

---

### Task 6: Extend `seed.py` for richer YAML

**Files:**
- Modify: `src/capability_commons/cli/seed.py`
- Create: `tests/test_ingest_load.py`

- [ ] **Step 1: Write failing tests for new seed.py behaviors**

Create `tests/test_ingest_load.py`:

```python
"""Tests for extended seed.py with ingestion YAML support."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.cli.seed import (
    SEED_TYPE_TO_CO_TYPE,
    build_structured_data,
    load_yaml_nodes,
    map_facets,
    resolve_co_type,
    resolve_requires,
)
from capability_commons.domain.enums import COType


class TestResolveCOType:
    def test_from_co_type_field(self):
        node = {"co_type": "PROJECT_BLUEPRINT"}
        assert resolve_co_type(node) == COType.PROJECT_BLUEPRINT

    def test_from_type_field_fallback(self):
        node = {"type": "skill"}
        assert resolve_co_type(node) == COType.SKILL_GUIDE

    def test_co_type_takes_precedence(self):
        node = {"co_type": "MODULE", "type": "concept"}
        assert resolve_co_type(node) == COType.MODULE

    def test_unknown_type_raises(self):
        with pytest.raises((KeyError, ValueError)):
            resolve_co_type({"type": "nonexistent"})


class TestResolveRequires:
    def test_flat_list(self):
        node = {"id": "water.test", "requires": ["a.b", "c.d"]}
        triples = resolve_requires(node)
        assert triples == [
            ("water.test", "a.b", {}),
            ("water.test", "c.d", {}),
        ]

    def test_grouped_format_preserves_mode(self):
        node = {
            "id": "water.test",
            "requires": [{"mode": "all_of", "ids": ["a.b", "c.d"]}],
        }
        triples = resolve_requires(node)
        assert ("water.test", "a.b", {"group_mode": "all_of"}) in triples
        assert ("water.test", "c.d", {"group_mode": "all_of"}) in triples

    def test_empty_requires(self):
        node = {"id": "test", "requires": []}
        assert resolve_requires(node) == []

    def test_no_requires_field(self):
        node = {"id": "test"}
        assert resolve_requires(node) == []


class TestBuildStructuredData:
    def test_markdown_body_used_when_present(self):
        node = {
            "markdown_body": "# Real content\nWith paragraphs.",
            "summary": "Short summary",
        }
        body = node.get("markdown_body") or node.get("summary", "")
        assert body == "# Real content\nWith paragraphs."

    def test_fallback_to_summary(self):
        node = {"summary": "Short summary"}
        body = node.get("markdown_body") or node.get("summary", "")
        assert body == "Short summary"

    def test_structured_data_merges_with_payload(self):
        node = {
            "payload": {"tools": ["hammer"]},
            "structured_data": {"goal": "build a thing"},
        }
        sd = build_structured_data(node)
        assert sd["tools"] == ["hammer"]
        assert sd["goal"] == "build a thing"

    def test_bundle_overrides_stored(self):
        node = {
            "bundle_overrides": {"hook": "Why this matters"},
        }
        sd = build_structured_data(node)
        assert sd["_bundle"]["hook"] == "Why this matters"

    def test_summary_long_not_in_structured_data(self):
        """summary_long goes to the ORM column, not structured_data."""
        node = {"summary_long": "A very long summary..."}
        sd = build_structured_data(node)
        assert "summary_long" not in sd  # handled by ORM field directly
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_load.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_co_type'`

- [ ] **Step 3: Implement seed.py extensions**

Modify `src/capability_commons/cli/seed.py`:

**Add `resolve_co_type` function** (after `RISK_MAP`):

```python
def resolve_co_type(node: dict) -> COType:
    """Resolve object type from co_type or type field."""
    if co_type_str := node.get("co_type"):
        return COType(co_type_str)
    return SEED_TYPE_TO_CO_TYPE[node["type"]]


def resolve_requires(node: dict) -> list[tuple[str, str, dict]]:
    """Extract (source_slug, target_slug, metadata) triples from requires field.

    Handles both flat list format:
        requires: ["a.b", "c.d"]

    And grouped format:
        requires:
          - mode: all_of
            ids: ["a.b", "c.d"]
    """
    src_slug = node["id"]
    triples: list[tuple[str, str, dict]] = []
    for item in node.get("requires", []):
        if isinstance(item, str):
            triples.append((src_slug, item, {}))
        elif isinstance(item, dict):
            mode = item.get("mode", "all_of")
            for req_id in item.get("ids", []):
                triples.append((src_slug, req_id, {"group_mode": mode}))
    return triples
```

**Update `build_structured_data`** to handle new fields:

```python
def build_structured_data(node: dict) -> dict:
    sd: dict = {}
    if payload := node.get("payload"):
        sd.update(payload)
    if structured := node.get("structured_data"):
        sd.update(structured)
    if tags := node.get("tags"):
        sd["tags"] = tags
    if outputs := node.get("outputs"):
        sd["outputs"] = outputs
    if bundle_overrides := node.get("bundle_overrides"):
        sd["_bundle"] = bundle_overrides
    # Note: summary_long is handled by the ORM column directly, not structured_data
    return sd
```

**Update `seed_graph`** — replace `co_type = SEED_TYPE_TO_CO_TYPE[node["type"]]` (line 171) with:

```python
            co_type = resolve_co_type(node)
```

**Update `seed_graph`** — replace the markdown_body line (line 193) with:

```python
                markdown_body=node.get("markdown_body") or node.get("summary", ""),
```

**Update `seed_graph`** — add `summary_medium` handling in the ContextObjectVersion creation:

```python
                summary_medium=node.get("summary_medium"),
```

**Update `seed_graph`** — replace the REQUIRES edge loop (lines 237-266) to use `resolve_requires`:

```python
        req_edges = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            for _, req_id, meta in resolve_requires(node):
                if req_id not in slug_to_version_id:
                    print(f"  WARN: missing prerequisite target {req_id}")
                    continue
                src_vid = slug_to_version_id[src_slug]
                dst_vid = slug_to_version_id[req_id]
                if await _edge_exists(src_vid, EdgeType.PREREQUISITE_FOR, dst_vid):
                    continue
                edge = Edge(
                    workspace_id=workspace.id,
                    src_node_kind=NodeKind.OBJECT_VERSION,
                    src_id=src_vid,
                    edge_type=EdgeType.PREREQUISITE_FOR,
                    dst_node_kind=NodeKind.OBJECT_VERSION,
                    dst_id=dst_vid,
                    ordinal=req_edges,
                    confidence=Decimal("1.0"),
                    provenance_method=ProvenanceMethod.HUMAN_AUTHORED,
                    status=RelationStatus.CURRENT,
                    metadata_json=meta,
                )
                session.add(edge)
                req_edges += 1
```

**Update CSV edge loading** — read confidence when present (around line 306):

```python
            conf_str = row.get("confidence", "")
            try:
                confidence = Decimal(conf_str) if conf_str else Decimal("1.0")
            except Exception:
                confidence = Decimal("1.0")
```

And use `confidence=confidence` instead of `confidence=Decimal("1.0")`.

**Add `lifecycle_state` handling** — in the ContextObject creation (around line 177):

```python
            lifecycle_str = node.get("lifecycle_state", "PUBLISHED")
            lifecycle = LifecycleState(lifecycle_str) if lifecycle_str else LifecycleState.PUBLISHED
```

And use `lifecycle_state=lifecycle` instead of `lifecycle_state=LifecycleState.PUBLISHED`.

**Add `summary_long` handling** — in the ContextObjectVersion creation:

```python
                summary_long=node.get("summary_long"),
```

**Add `suggested_edges` handling** — after the REQUIRES edge loop, add:

```python
        # --- suggested_edges from ingestion YAML ---
        sug_edges = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            for edge_spec in node.get("suggested_edges", []):
                target_id = edge_spec.get("target_id")
                edge_type_str = edge_spec.get("edge_type", "builds_on")
                if target_id not in slug_to_version_id:
                    print(f"  WARN: missing suggested_edge target {target_id}")
                    continue
                src_vid = slug_to_version_id[src_slug]
                dst_vid = slug_to_version_id[target_id]
                try:
                    et = EdgeType(edge_type_str.upper())
                except ValueError:
                    print(f"  WARN: unknown edge type {edge_type_str}")
                    continue
                if await _edge_exists(src_vid, et, dst_vid):
                    continue
                edge = Edge(
                    workspace_id=workspace.id,
                    src_node_kind=NodeKind.OBJECT_VERSION,
                    src_id=src_vid,
                    edge_type=et,
                    dst_node_kind=NodeKind.OBJECT_VERSION,
                    dst_id=dst_vid,
                    ordinal=sug_edges,
                    confidence=Decimal(str(edge_spec.get("confidence", 0.8))),
                    provenance_method=ProvenanceMethod.LLM_GENERATED,
                    status=RelationStatus.CURRENT,
                    metadata_json={},
                )
                session.add(edge)
                sug_edges += 1
        if sug_edges:
            print(f"  Created {sug_edges} suggested edges")
```

**Add citation/evidence handling** — after the suggested_edges loop, add:

```python
        # --- citations → EvidenceSource + EvidenceSpan ---
        cit_count = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            version_id = slug_to_version_id[src_slug]
            for citation in node.get("citations", []):
                for span in citation.get("support", []):
                    source_ext_id = span.get("source_id", "")
                    # Find-or-create EvidenceSource by external_id
                    es_result = await session.execute(
                        select(EvidenceSource).where(
                            EvidenceSource.external_id == source_ext_id
                        )
                    )
                    ev_source = es_result.scalar_one_or_none()
                    if ev_source is None:
                        ev_source = EvidenceSource(
                            workspace_id=workspace.id,
                            external_id=source_ext_id,
                            source_kind=SourceKind.BOOK,
                            uri=source_ext_id,
                            metadata_json={},
                        )
                        session.add(ev_source)
                        await session.flush()

                    # Create EvidenceSpan
                    ev_span = EvidenceSpan(
                        source_id=ev_source.id,
                        content_object_version_id=version_id,
                        page_start=span.get("page_start"),
                        page_end=span.get("page_end"),
                        start_char=span.get("start_char"),
                        end_char=span.get("end_char"),
                        excerpt=span.get("excerpt", ""),
                        metadata_json={
                            "segment_id": span.get("segment_id", ""),
                            "claim_id": citation.get("claim_id", ""),
                            "claim_text": citation.get("claim_text", ""),
                            "support_strength": span.get("support_strength", ""),
                        },
                    )
                    session.add(ev_span)
                    cit_count += 1
        if cit_count:
            print(f"  Created {cit_count} evidence spans")
```

Note: This requires importing `EvidenceSource`, `EvidenceSpan`, and `SourceKind` at the top of `seed.py`. Add:

```python
from capability_commons.db.models import EvidenceSource, EvidenceSpan
from capability_commons.domain.enums import SourceKind
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_load.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run existing seed tests to verify backwards compatibility**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_seed.py -v`
Expected: All existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/cli/seed.py tests/test_ingest_load.py
git commit -m "feat: extend seed.py for richer ingestion YAML (co_type, flat requires, citations, bundles)"
```

---

### Task 7: Implement Pass 0 — PDF parsing

**Files:**
- Create: `src/capability_commons/cli/ingest/parse.py`
- Create: `tests/test_ingest_parse.py`
- Create: `tests/fixtures/ingest/test.pdf` (tiny test PDF)

- [ ] **Step 1: Create a minimal test PDF fixture**

```bash
cd ~/Projects/CapabilityCommons
mkdir -p tests/fixtures/ingest
python3 -c "
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/ingest/test.pdf', pagesize=letter)
c.setFont('Helvetica-Bold', 16)
c.drawString(72, 700, 'Chapter 1: Water Storage')
c.setFont('Helvetica', 12)
c.drawString(72, 670, 'Water should be stored in food-grade containers.')
c.drawString(72, 650, 'Store at least one gallon per person per day.')
c.setFont('Helvetica-Bold', 14)
c.drawString(72, 610, 'Section 1.1: Container Selection')
c.setFont('Helvetica', 12)
c.drawString(72, 590, 'Use BPA-free plastic or glass containers.')
c.drawString(72, 570, 'Avoid containers previously used for chemicals.')
c.save()
"
```

If `reportlab` is not installed, create a simple text-based test instead and skip the actual PDF parsing integration test (mark with `@pytest.mark.skipif`).

- [ ] **Step 2: Write tests for parse pass**

Create `tests/test_ingest_parse.py`:

```python
"""Tests for Pass 0: PDF parsing to segments."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import orjson
import pytest

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.parse import (
    markdown_to_segments,
    run_parse,
)
from capability_commons.cli.ingest.project import IngestProject


class TestMarkdownToSegments:
    def test_splits_on_headings(self):
        md = """# Chapter 1: Water Storage

Water should be stored safely.

## Section 1.1: Containers

Use food-grade containers.

## Section 1.2: Treatment

Treat water before storage.
"""
        segments = markdown_to_segments(
            md,
            source_id="src.test",
            base_page=1,
        )
        assert len(segments) >= 3
        assert segments[0].heading_path == ["Chapter 1: Water Storage"]
        assert "water" in segments[0].text.lower()

    def test_assigns_sequential_ids(self):
        md = "# A\nText A\n# B\nText B\n# C\nText C\n"
        segments = markdown_to_segments(md, source_id="src.test", base_page=1)
        ids = [s.segment_id for s in segments]
        assert ids == ["seg_000001", "seg_000002", "seg_000003"]

    def test_preserves_page_boundaries(self):
        md = "# Heading\nSome text on page 5."
        segments = markdown_to_segments(md, source_id="src.test", base_page=5)
        assert segments[0].page_start == 5


class TestRunParse:
    def test_writes_segments_jsonl(self, tmp_path):
        projects_root = tmp_path / "projects"
        proj = IngestProject.init(
            projects_root=projects_root,
            name="test-parse",
            sources=[{
                "id": "src.test",
                "file": "sources/test.pdf",
                "title": "Test",
                "source_kind": "BOOK",
            }],
        )
        # Mock marker to return known markdown
        mock_md = "# Chapter 1\nSome content.\n## Section A\nMore content.\n"
        with patch(
            "capability_commons.cli.ingest.parse.convert_pdf_to_markdown",
            return_value={"markdown": mock_md, "pages": [{"page": 1}]},
        ):
            run_parse(proj)

        assert proj.segments_file.exists()
        lines = proj.segments_file.read_text().strip().split("\n")
        assert len(lines) >= 2
        seg = SourceSegment.model_validate(orjson.loads(lines[0]))
        assert seg.source_id == "src.test"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_parse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement parse.py**

Create `src/capability_commons/cli/ingest/parse.py`:

```python
"""Pass 0: Parse PDFs into page-preserving markdown segments."""
from __future__ import annotations

import re
from pathlib import Path

import orjson
import yaml

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject


def convert_pdf_to_markdown(pdf_path: str) -> dict:
    """Convert a PDF to markdown using marker. Thin wrapper for mockability."""
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
    except ImportError:
        raise ImportError(
            "marker-pdf is required for PDF parsing. "
            "Install with: pip install -e '.[ingest]'"
        )

    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(pdf_path)
    return {
        "markdown": rendered.markdown,
        "pages": [{"page": i + 1} for i in range(len(rendered.pages))],
    }


def markdown_to_segments(
    markdown: str,
    source_id: str,
    base_page: int = 1,
) -> list[SourceSegment]:
    """Split markdown into segments at heading boundaries."""
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    segments: list[SourceSegment] = []

    # Find all heading positions
    splits: list[tuple[int, list[str]]] = []
    heading_stack: list[str] = []

    for match in heading_re.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        # Maintain heading stack by level
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        splits.append((match.start(), list(heading_stack)))

    if not splits:
        # No headings — treat the whole thing as one segment
        if markdown.strip():
            segments.append(SourceSegment(
                source_id=source_id,
                segment_id="seg_000001",
                page_start=base_page,
                page_end=base_page,
                heading_path=[],
                text=markdown.strip(),
                start_char=0,
                end_char=len(markdown.strip()),
            ))
        return segments

    # Build segments between headings
    for i, (start, heading_path) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(markdown)
        text = markdown[start:end].strip()
        if not text:
            continue

        seg_num = i + 1
        segments.append(SourceSegment(
            source_id=source_id,
            segment_id=f"seg_{seg_num:06d}",
            page_start=base_page,
            page_end=base_page,
            heading_path=heading_path,
            text=text,
            start_char=start,
            end_char=end,
        ))

    return segments


def run_parse(project: IngestProject) -> None:
    """Execute Pass 0: parse all source PDFs into segments."""
    from rich.console import Console

    console = Console()
    all_segments: list[SourceSegment] = []
    source_records: list[dict] = []

    for source in project.manifest.sources:
        source_path = project.root / source.file
        console.print(f"  Parsing [bold]{source.file}[/bold]...")

        if source_path.suffix.lower() == ".pdf":
            result = convert_pdf_to_markdown(str(source_path))
            markdown = result["markdown"]
            n_pages = len(result.get("pages", []))
        else:
            # Assume text/markdown file
            markdown = source_path.read_text()
            n_pages = 1

        segments = markdown_to_segments(markdown, source.id)
        all_segments.extend(segments)

        source_records.append({
            "source_id": source.id,
            "title": source.title,
            "source_kind": source.source_kind,
            "file": source.file,
            "pages": n_pages,
            "segments": len(segments),
        })
        console.print(f"    → {len(segments)} segments from {n_pages} pages")

    # Write segments JSONL
    with open(project.segments_file, "wb") as f:
        for seg in all_segments:
            f.write(orjson.dumps(seg.model_dump()) + b"\n")

    # Write source manifest
    source_manifest_path = project.segments_dir / "source_manifest.yaml"
    with open(source_manifest_path, "w") as f:
        yaml.dump(source_records, f, default_flow_style=False)

    project.mark_pass_complete("parse")
    console.print(f"[green]Parse complete:[/green] {len(all_segments)} segments from {len(project.manifest.sources)} source(s)")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_parse.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/capability_commons/cli/ingest/parse.py \
        tests/test_ingest_parse.py
git commit -m "feat(ingest): add Pass 0 — PDF parsing to segments"
```

---

### Task 8: Implement validate and status commands

**Files:**
- Create: `src/capability_commons/cli/ingest/validate.py` (combined validate + status logic)

- [ ] **Step 1: Implement validate.py**

Create `src/capability_commons/cli/ingest/validate.py`:

```python
"""Validate and status commands for ingestion projects."""
from __future__ import annotations

from pathlib import Path

import orjson
import yaml
from rich.console import Console
from rich.table import Table

from capability_commons.cli.ingest.models import ValidationReport
from capability_commons.cli.ingest.project import IngestProject

# Valid enum values from domain/enums.py
VALID_CO_TYPES = {
    "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
    "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
    "field_report", "worksheet", "glossary", "safety_notice", "correction",
}
VALID_STAGES = {"foundation", "household", "productive", "community", "advanced"}
VALID_COST_BANDS = {"free", "low", "medium", "high"}
VALID_RISK_BANDS = {"low", "moderate", "high", "expert_only"}
VALID_LIFECYCLE = {"DRAFT", "IN_REVIEW", "REVIEWED", "VERIFIED", "PUBLISHED", "DEPRECATED", "ARCHIVED"}


def run_validate(project: IngestProject) -> ValidationReport:
    """Validate all drafts and edges in a project."""
    errors: list[str] = []
    warnings: list[str] = []

    # Load drafts
    drafts_dir = project.drafts_dir
    draft_files = sorted(drafts_dir.glob("*.yaml"))
    draft_slugs: set[str] = set()
    objects_with_citations = 0
    total_citations = 0

    for draft_file in draft_files:
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)
        draft_slugs.add(slug)

        # Required fields
        if not obj.get("canonical_title") and not obj.get("title"):
            errors.append(f"{slug}: missing title/canonical_title")
        if not obj.get("plain_language"):
            warnings.append(f"{slug}: missing plain_language")

        # Valid enum values
        co_type = obj.get("co_type", obj.get("candidate_type", ""))
        if co_type and co_type.lower().replace(" ", "_") not in VALID_CO_TYPES:
            errors.append(f"{slug}: invalid type '{co_type}'")

        stage = obj.get("stage", "")
        if stage and stage not in VALID_STAGES:
            errors.append(f"{slug}: invalid stage '{stage}'")

        cost = obj.get("cost_band", "")
        if cost and cost not in VALID_COST_BANDS:
            errors.append(f"{slug}: invalid cost_band '{cost}'")

        risk = obj.get("risk_band", "")
        if risk and risk not in VALID_RISK_BANDS:
            errors.append(f"{slug}: invalid risk_band '{risk}'")

        lifecycle = obj.get("lifecycle_state", "")
        if lifecycle and lifecycle not in VALID_LIFECYCLE:
            errors.append(f"{slug}: invalid lifecycle_state '{lifecycle}'")

        # Citation coverage
        citations = obj.get("citations", [])
        if citations:
            objects_with_citations += 1
            total_citations += len(citations)
        else:
            warnings.append(f"{slug}: no citations")

        # Safety checks
        failure_modes = obj.get("structured_data", {}).get("failure_modes") or obj.get("payload", {}).get("failure_modes")
        if failure_modes and not risk:
            warnings.append(f"{slug}: has failure_modes but no risk_band")
        if risk in ("high", "expert_only"):
            safety = obj.get("structured_data", {}).get("safety_boundary") or obj.get("payload", {}).get("safety_boundary")
            if not safety:
                warnings.append(f"{slug}: risk_band={risk} but no safety_boundary")

    # Validate edges
    edges_count = 0
    if project.edges_file.exists():
        import polars as pl
        edges_df = pl.read_csv(project.edges_file)
        edges_count = len(edges_df)
        for row in edges_df.iter_rows(named=True):
            if row["source_id"] not in draft_slugs:
                errors.append(f"Edge source '{row['source_id']}' not in drafts")
            if row["target_id"] not in draft_slugs:
                errors.append(f"Edge target '{row['target_id']}' not in drafts")

    objects_count = len(draft_files)
    coverage = objects_with_citations / objects_count if objects_count > 0 else 0.0

    return ValidationReport(
        objects_count=objects_count,
        edges_count=edges_count,
        citations_count=total_citations,
        errors=errors,
        warnings=warnings,
        citation_coverage=coverage,
    )


def print_validation_report(report: ValidationReport, console: Console | None = None) -> None:
    """Print a formatted validation report."""
    console = console or Console()

    console.print(f"\n[bold]Validation Report[/bold]")
    console.print(f"  Objects: {report.objects_count}")
    console.print(f"  Edges: {report.edges_count}")
    console.print(f"  Citations: {report.citations_count}")
    console.print(f"  Citation coverage: {report.citation_coverage:.0%}")

    if report.errors:
        console.print(f"\n[red bold]Errors ({len(report.errors)}):[/red bold]")
        for e in report.errors:
            console.print(f"  [red]✗[/red] {e}")

    if report.warnings:
        console.print(f"\n[yellow bold]Warnings ({len(report.warnings)}):[/yellow bold]")
        for w in report.warnings:
            console.print(f"  [yellow]![/yellow] {w}")

    if not report.errors:
        console.print("\n[green bold]✓ No errors found[/green bold]")


def run_status(project: IngestProject) -> None:
    """Print a status table for all passes."""
    console = Console()
    table = Table(title=f"Project: {project.manifest.name}")
    table.add_column("Pass", style="bold")
    table.add_column("Status")
    table.add_column("Files")

    pass_info = [
        ("parse", project.segments_file, "segments"),
        ("extract", project.matrix_file, "matrix rows"),
        ("draft", project.drafts_dir, "objects"),
        ("cite", project.evidence_map_file, "citations"),
        ("canonicalize", project.drafts_dir / "canonicalization_log.json", "decisions"),
        ("edges", project.edges_file, "edges"),
        ("bundles", project.drafts_dir, "bundles"),
        ("load", project.output_dir / "canonical" / "nodes", "loaded"),
    ]

    for pass_name, path, label in pass_info:
        status_obj = getattr(project.manifest.passes, pass_name)
        if status_obj.completed:
            status = f"[green]✓ {status_obj.completed:%Y-%m-%d %H:%M}[/green]"
        else:
            status = "[dim]pending[/dim]"

        # Count files
        count = ""
        if path.is_file() and path.exists():
            if path.suffix == ".jsonl":
                count = str(len(path.read_text().strip().splitlines()))
            elif path.suffix == ".csv":
                count = str(max(0, len(path.read_text().strip().splitlines()) - 1))
            elif path.suffix == ".json":
                count = "1"
            count = f"{count} {label}"
        elif path.is_dir() and path.exists():
            yaml_count = len(list(path.glob("*.yaml")))
            if yaml_count:
                count = f"{yaml_count} {label}"

        table.add_row(pass_name, status, count)

    console.print(table)
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/validate.py
git commit -m "feat(ingest): add validate and status commands"
```

---

## Chunk 3: LLM Passes

### Task 9: Implement Pass 1 — extraction matrix generation

**Files:**
- Create: `src/capability_commons/cli/ingest/extract.py`

- [ ] **Step 1: Implement extract.py**

Create `src/capability_commons/cli/ingest/extract.py`:

```python
"""Pass 1: Generate extraction matrix from segments via LLM."""
from __future__ import annotations

import orjson
import polars as pl
from pydantic import BaseModel
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import ExtractionRow, SourceSegment
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are an extraction analyst for Capability Commons. "
    "Identify reproducible capabilities, practical concepts, projects, exercises, "
    "assessments, and adaptations. Output only valid JSON matching the requested schema. "
    "Do not invent sections, pages, or claims. Mark uncertainty explicitly. "
    "Do not copy long passages."
)

USER_TEMPLATE = """Project doctrine:
- The unit of value is the reproducible capability.
- Capability Commons maps concepts -> skills -> projects -> local deployment -> teach-forward.
- Preferred object types: concept_note, skill_guide, project_blueprint, reference_sheet, module, assessment, learning_path, field_report, local_adaptation, teach_forward_packet.

For each provided section:
1. identify candidate objects
2. classify type
3. decide split vs merge
4. list key concepts, key actions, tools, risks, local adaptation signals
5. propose canonical slug (format: domain.topic-name)
6. include source page range and segment IDs

Return a JSON object with key "rows" containing an array of extraction rows.

Extraction row schema:
{schema}

SOURCE SECTION:
{section_text}"""


class ExtractionResponse(BaseModel):
    rows: list[ExtractionRow]


def group_segments_by_section(
    segments: list[SourceSegment],
    depth: int = 2,
) -> dict[str, list[SourceSegment]]:
    """Group segments by their heading path up to the given depth."""
    sections: dict[str, list[SourceSegment]] = {}
    for seg in segments:
        key = " > ".join(seg.heading_path[:depth]) if seg.heading_path else "(untitled)"
        sections.setdefault(key, []).append(seg)
    return sections


async def run_extract(
    project: IngestProject,
    client: LLMClient,
    sections_filter: str | None = None,
    yes: bool = False,
) -> None:
    """Execute Pass 1: segments → extraction matrix."""
    console = Console()

    # Load segments
    segments: list[SourceSegment] = []
    with open(project.segments_file) as f:
        for line in f:
            segments.append(SourceSegment.model_validate(orjson.loads(line)))

    # Group into sections
    section_groups = group_segments_by_section(segments)

    # Apply filter
    if sections_filter:
        section_groups = {
            k: v for k, v in section_groups.items()
            if sections_filter.lower() in k.lower()
        }

    console.print(f"  {len(section_groups)} sections to process")

    # Estimate tokens
    total_text = "\n".join(
        seg.text for segs in section_groups.values() for seg in segs
    )
    est_tokens = client.estimate_tokens(total_text + SYSTEM_PROMPT + USER_TEMPLATE)
    console.print(f"  Estimated input tokens: ~{est_tokens:,}")

    if not yes:
        confirm = input("  Proceed? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Generate matrix
    schema_json = ExtractionRow.model_json_schema()
    all_rows: list[dict] = []

    for section_name, section_segments in section_groups.items():
        section_text = "\n\n".join(
            f"[{seg.segment_id} | pages {seg.page_start}-{seg.page_end}]\n{seg.text}"
            for seg in section_segments
        )
        user_msg = USER_TEMPLATE.format(
            schema=orjson.dumps(schema_json).decode(),
            section_text=section_text,
        )

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=ExtractionResponse,
            )
            for row in result.rows:
                all_rows.append(row.model_dump())
            console.print(f"    [green]✓[/green] {section_name}: {len(result.rows)} rows")
        except Exception as e:
            console.print(f"    [red]✗[/red] {section_name}: {e}")

    # Write CSV
    if all_rows:
        df = pl.DataFrame(all_rows)
        # Serialize list columns as pipe-delimited strings for CSV
        for col in df.columns:
            if df[col].dtype == pl.List:
                df = df.with_columns(
                    pl.col(col).list.join("|").alias(col)
                )
        df.write_csv(project.matrix_file)

    project.mark_pass_complete("extract")
    console.print(f"[green]Extract complete:[/green] {len(all_rows)} rows written")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/extract.py
git commit -m "feat(ingest): add Pass 1 — extraction matrix generation"
```

---

### Task 10: Implement Pass 2 — canonical object drafting

**Files:**
- Create: `src/capability_commons/cli/ingest/draft.py`

- [ ] **Step 1: Implement draft.py**

Create `src/capability_commons/cli/ingest/draft.py`:

```python
"""Pass 2: Draft canonical YAML objects from extraction matrix via LLM."""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import orjson
import polars as pl
import yaml
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a Capability Commons object drafter. Convert source material into "
    "learner-facing, plain-language canonical objects. Preserve accuracy. "
    "Do not invent unsupported steps or numbers. Do not copy long passages. "
    "Separate universal guidance from local adaptation. Output only valid JSON."
)

USER_TEMPLATE = """Target object YAML schema fields:
- id, seed_type, co_type, slug, canonical_title, version_no (1), lifecycle_state (DRAFT)
- visibility (public), language_code (en), primary_domain, secondary_domains, stage
- contexts, difficulty (1-5), cost_band, risk_band
- summary_short, summary_medium, plain_language
- markdown_body (with sections: What this is, Why it matters, What you need, How to do it, Common failure modes, Safety/boundary notes, Local adaptation notes)
- structured_data (type-specific: tools, materials, success_criteria, failure_modes, safety_boundary for skills; goal, deliverables, acceptance_criteria for projects; definition, key_questions, misconceptions for concepts)
- requires (flat list of prerequisite slugs)
- suggested_edges (list of {{target_id, edge_type}})
- citations (empty list — will be populated in citation pass)

Candidate from extraction matrix:
{matrix_row}

Supporting source segments:
{segments}

Return a JSON object with all the fields listed above. The markdown_body should contain real explanatory content synthesized from the source segments, not just a summary."""


async def run_draft(
    project: IngestProject,
    client: LLMClient,
    skip_existing: bool = False,
    slugs_filter: str | None = None,
    yes: bool = False,
) -> None:
    """Execute Pass 2: extraction matrix → canonical YAML objects."""
    console = Console()

    # Load matrix
    df = pl.read_csv(project.matrix_file)
    console.print(f"  {len(df)} rows in extraction matrix")

    # Load segments for lookup
    segments_by_id: dict[str, SourceSegment] = {}
    with open(project.segments_file) as f:
        for line in f:
            seg = SourceSegment.model_validate(orjson.loads(line))
            segments_by_id[seg.segment_id] = seg

    # Estimate tokens
    total_text = ""
    rows_to_process = []
    for row in df.iter_rows(named=True):
        slug = row["candidate_slug"]
        if slugs_filter and not fnmatch(slug, slugs_filter):
            continue
        if skip_existing and (project.drafts_dir / f"{slug}.yaml").exists():
            continue
        rows_to_process.append(row)
        # Gather segment text for estimation
        seg_ids = row.get("segment_ids", "").split("|") if row.get("segment_ids") else []
        for sid in seg_ids:
            if sid in segments_by_id:
                total_text += segments_by_id[sid].text

    est_tokens = client.estimate_tokens(total_text + SYSTEM_PROMPT + USER_TEMPLATE)
    console.print(f"  {len(rows_to_process)} objects to draft (~{est_tokens:,} input tokens)")

    if not rows_to_process:
        console.print("[dim]Nothing to draft.[/dim]")
        return

    if not yes:
        confirm = input("  Proceed? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Draft objects
    from pydantic import BaseModel

    class DraftObject(BaseModel, extra="allow"):
        id: str
        slug: str
        canonical_title: str
        markdown_body: str

    drafted = 0
    for row in rows_to_process:
        slug = row["candidate_slug"]
        seg_ids = row.get("segment_ids", "").split("|") if row.get("segment_ids") else []
        segment_texts = "\n\n".join(
            f"[{sid} | pages {segments_by_id[sid].page_start}-{segments_by_id[sid].page_end}]\n{segments_by_id[sid].text}"
            for sid in seg_ids
            if sid in segments_by_id
        )

        user_msg = USER_TEMPLATE.format(
            matrix_row=orjson.dumps(row).decode(),
            segments=segment_texts or "(no segments available)",
        )

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=DraftObject,
            )
            # Write as YAML
            draft_path = project.drafts_dir / f"{slug}.yaml"
            with open(draft_path, "w") as f:
                yaml.dump(
                    result.model_dump(),
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            drafted += 1
            console.print(f"    [green]✓[/green] {slug}")
        except Exception as e:
            console.print(f"    [red]✗[/red] {slug}: {e}")

    project.mark_pass_complete("draft")
    console.print(f"[green]Draft complete:[/green] {drafted} objects written")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/draft.py
git commit -m "feat(ingest): add Pass 2 — canonical object drafting"
```

---

### Task 11: Implement Pass 3 — citation linking

**Files:**
- Create: `src/capability_commons/cli/ingest/cite.py`

- [ ] **Step 1: Implement cite.py**

Create `src/capability_commons/cli/ingest/cite.py`:

```python
"""Pass 3: Link claims in drafts to source spans via LLM."""
from __future__ import annotations

from fnmatch import fnmatch

import orjson
import yaml
from pydantic import BaseModel
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import ClaimCitation, SourceSegment
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a citation linker. For each drafted claim, attach one or more "
    "supporting source spans. Do not invent citations. If support is partial, "
    "say so. If no support exists, return NO_SUPPORT for that claim. "
    "Output only valid JSON."
)

USER_TEMPLATE = """Object draft:
{draft_object}

Available source segments:
{segments}

For each substantive claim in the object's markdown_body (facts, procedures, cautions), return a JSON object with key "citations" containing an array where each item has:
- object_id: the object slug
- claim_id: a sequential ID like clm_001
- claim_text: the claim being cited
- support: array of {{source_id, page_start, page_end, segment_id, excerpt, start_char, end_char, support_strength}}

support_strength must be "strong", "medium", or "weak"."""


class CitationResponse(BaseModel):
    citations: list[ClaimCitation]


async def run_cite(
    project: IngestProject,
    client: LLMClient,
    slugs_filter: str | None = None,
    yes: bool = False,
) -> None:
    """Execute Pass 3: drafts → citation/evidence linking."""
    console = Console()

    # Load segments
    segments_by_id: dict[str, SourceSegment] = {}
    with open(project.segments_file) as f:
        for line in f:
            seg = SourceSegment.model_validate(orjson.loads(line))
            segments_by_id[seg.segment_id] = seg

    # Load drafts
    draft_files = sorted(project.drafts_dir.glob("*.yaml"))
    if slugs_filter:
        draft_files = [f for f in draft_files if fnmatch(f.stem, slugs_filter)]

    console.print(f"  {len(draft_files)} drafts to process")

    if not draft_files:
        console.print("[dim]Nothing to cite.[/dim]")
        return

    if not yes:
        confirm = input("  Proceed? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    all_citations: list[dict] = []

    for draft_file in draft_files:
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)

        # Collect relevant segments (from the object's source references)
        source_id = obj.get("source_id") or (
            project.manifest.sources[0].id if project.manifest.sources else ""
        )
        relevant_segs = [
            s for s in segments_by_id.values() if s.source_id == source_id
        ]
        # Limit to reasonable context
        segments_text = "\n\n".join(
            f"[{s.segment_id} | pages {s.page_start}-{s.page_end}]\n{s.text}"
            for s in relevant_segs[:50]
        )

        user_msg = USER_TEMPLATE.format(
            draft_object=yaml.dump(obj, default_flow_style=False),
            segments=segments_text or "(no segments available)",
        )

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=CitationResponse,
            )
            # Patch citations into draft YAML
            obj["citations"] = [c.model_dump() for c in result.citations]
            with open(draft_file, "w") as f:
                yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            all_citations.extend(c.model_dump() for c in result.citations)
            console.print(f"    [green]✓[/green] {slug}: {len(result.citations)} citations")
        except Exception as e:
            console.print(f"    [red]✗[/red] {slug}: {e}")

    # Write evidence map
    with open(project.evidence_map_file, "wb") as f:
        f.write(orjson.dumps(all_citations, option=orjson.OPT_INDENT_2))

    project.mark_pass_complete("cite")
    console.print(f"[green]Cite complete:[/green] {len(all_citations)} citations linked")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/cite.py
git commit -m "feat(ingest): add Pass 3 — citation linking"
```

---

### Task 12: Implement Pass 4 — canonicalization

**Files:**
- Create: `src/capability_commons/cli/ingest/canonicalize.py`

- [ ] **Step 1: Implement canonicalize.py**

Create `src/capability_commons/cli/ingest/canonicalize.py`:

```python
"""Pass 4: Canonicalize and deduplicate drafts via LLM + fuzzy matching."""
from __future__ import annotations

import shutil

import orjson
import yaml
from pydantic import BaseModel
from rapidfuzz import fuzz
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import CanonicalizationDecision
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a corpus editor. Merge duplicates and split overloaded drafts "
    "while preserving provenance. Choose one canonical slug. Do not discard "
    "source support. Output only valid JSON."
)

USER_TEMPLATE = """These drafts appear similar. For each group, decide:
- "keep": both are distinct, no changes needed
- "merge": combine into one canonical object (provide the merged object)
- "split": one object should be split into multiple (provide the split objects)

Return a JSON object with key "decisions" containing an array of decisions.
Each decision: {{action, rationale, canonical_slug, deprecated_draft_ids}}

Draft set:
{drafts}"""

SIMILARITY_THRESHOLD = 75  # rapidfuzz ratio threshold


class CanonicalizeResponse(BaseModel):
    decisions: list[CanonicalizationDecision]


def find_similar_groups(
    drafts: dict[str, dict],
    threshold: int = SIMILARITY_THRESHOLD,
) -> list[list[str]]:
    """Group drafts by title/summary similarity using rapidfuzz."""
    slugs = list(drafts.keys())
    visited: set[str] = set()
    groups: list[list[str]] = []

    for i, slug_a in enumerate(slugs):
        if slug_a in visited:
            continue
        group = [slug_a]
        title_a = drafts[slug_a].get("canonical_title", "")
        summary_a = drafts[slug_a].get("summary_short", "")
        domain_a = drafts[slug_a].get("primary_domain", "")

        for slug_b in slugs[i + 1:]:
            if slug_b in visited:
                continue
            domain_b = drafts[slug_b].get("primary_domain", "")
            if domain_a != domain_b:
                continue
            title_b = drafts[slug_b].get("canonical_title", "")
            summary_b = drafts[slug_b].get("summary_short", "")
            title_sim = fuzz.ratio(title_a, title_b)
            summary_sim = fuzz.ratio(summary_a, summary_b)
            if max(title_sim, summary_sim) >= threshold:
                group.append(slug_b)
                visited.add(slug_b)

        if len(group) > 1:
            groups.append(group)
        visited.add(slug_a)

    return groups


async def run_canonicalize(
    project: IngestProject,
    client: LLMClient,
    yes: bool = False,
) -> None:
    """Execute Pass 4: deduplicate and canonicalize drafts."""
    console = Console()

    # Load all drafts
    drafts: dict[str, dict] = {}
    for draft_file in sorted(project.drafts_dir.glob("*.yaml")):
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)
        drafts[slug] = obj

    console.print(f"  {len(drafts)} drafts loaded")

    # Find similar groups
    groups = find_similar_groups(drafts)
    console.print(f"  {len(groups)} potentially similar groups found")

    if not groups:
        console.print("[dim]No duplicates detected.[/dim]")
        project.mark_pass_complete("canonicalize")
        return

    if not yes:
        confirm = input("  Proceed with LLM review? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Ensure subdirectories exist
    merged_dir = project.drafts_dir / "_merged"
    split_dir = project.drafts_dir / "_split"
    merged_dir.mkdir(exist_ok=True)
    split_dir.mkdir(exist_ok=True)

    all_decisions: list[dict] = []

    for group in groups:
        group_drafts = {slug: drafts[slug] for slug in group}
        drafts_text = "\n---\n".join(
            yaml.dump(obj, default_flow_style=False) for obj in group_drafts.values()
        )

        user_msg = USER_TEMPLATE.format(drafts=drafts_text)

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=CanonicalizeResponse,
            )
            for decision in result.decisions:
                all_decisions.append(decision.model_dump())
                if decision.action == "merge":
                    for dep_id in decision.deprecated_draft_ids:
                        src = project.drafts_dir / f"{dep_id}.yaml"
                        if src.exists():
                            shutil.move(str(src), str(merged_dir / src.name))
                    console.print(
                        f"    [green]merge[/green] → {decision.canonical_slug} "
                        f"(deprecated: {decision.deprecated_draft_ids})"
                    )
                elif decision.action == "split":
                    for dep_id in decision.deprecated_draft_ids:
                        src = project.drafts_dir / f"{dep_id}.yaml"
                        if src.exists():
                            shutil.move(str(src), str(split_dir / src.name))
                    console.print(
                        f"    [blue]split[/blue] {decision.canonical_slug} "
                        f"(original: {decision.deprecated_draft_ids})"
                    )
                else:
                    console.print(f"    [dim]keep[/dim] {decision.canonical_slug}")
        except Exception as e:
            console.print(f"    [red]✗[/red] group {group}: {e}")

    # Write log
    log_path = project.drafts_dir / "canonicalization_log.json"
    with open(log_path, "wb") as f:
        f.write(orjson.dumps(all_decisions, option=orjson.OPT_INDENT_2))

    project.mark_pass_complete("canonicalize")
    console.print(f"[green]Canonicalize complete:[/green] {len(all_decisions)} decisions")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/canonicalize.py
git commit -m "feat(ingest): add Pass 4 — canonicalization and dedup"
```

---

### Task 13: Implement Pass 5 — edge extraction

**Files:**
- Create: `src/capability_commons/cli/ingest/edges.py`

- [ ] **Step 1: Implement edges.py**

Create `src/capability_commons/cli/ingest/edges.py`:

```python
"""Pass 5: Extract typed edges from the object set via LLM."""
from __future__ import annotations

import orjson
import polars as pl
import yaml
from pydantic import BaseModel
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import ExtractedEdge
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a graph editor. Infer only justified edges between already-drafted objects. "
    "Use: prerequisite_for, builds_on, next_step_for, contains, supported_by, derived_from, "
    "alternative_to, adapted_for, applies_in, requires_tool, requires_material, "
    "has_failure_mode, mitigated_by, unsafe_without, bounded_by, corrected_by, "
    "contradicted_by, supersedes. Output only valid JSON."
)

USER_TEMPLATE = """Given this set of knowledge objects, identify all justified edges between them.

Rules:
- prerequisite_for: B cannot be done safely without A
- builds_on: B benefits from A but doesn't strictly require it
- contains: a module/blueprint includes smaller objects
- alternative_to: two objects solve the same problem differently
- adapted_for: a region/budget/climate variant
- has_failure_mode: points to a failure description
- bounded_by: points to a constraint

Return a JSON object with key "edges" containing an array of:
{{source_id, target_id, edge_type, sequence (optional), condition (optional), confidence}}

Object set:
{objects}"""


class EdgesResponse(BaseModel):
    edges: list[ExtractedEdge]


async def run_edges(
    project: IngestProject,
    client: LLMClient,
    yes: bool = False,
) -> None:
    """Execute Pass 5: object set → typed edges."""
    console = Console()

    # Load drafts and build summaries
    summaries: list[dict] = []
    for draft_file in sorted(project.drafts_dir.glob("*.yaml")):
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)
        summaries.append({
            "slug": slug,
            "type": obj.get("co_type") or obj.get("seed_type", ""),
            "title": obj.get("canonical_title") or obj.get("title", ""),
            "summary": obj.get("summary_short", ""),
            "requires": obj.get("requires", []),
            "suggested_edges": obj.get("suggested_edges", []),
        })

    console.print(f"  {len(summaries)} objects for edge extraction")

    # Collect pre-existing suggested edges
    existing_edges: set[tuple[str, str, str]] = set()
    suggested: list[dict] = []
    for s in summaries:
        for edge in s.get("suggested_edges", []):
            key = (s["slug"], edge["target_id"], edge["edge_type"])
            if key not in existing_edges:
                existing_edges.add(key)
                suggested.append({
                    "source_id": s["slug"],
                    "target_id": edge["target_id"],
                    "edge_type": edge["edge_type"],
                    "confidence": edge.get("confidence", 0.8),
                })

    # Estimate and confirm
    objects_text = orjson.dumps(summaries).decode()
    est_tokens = client.estimate_tokens(objects_text + SYSTEM_PROMPT + USER_TEMPLATE)
    console.print(f"  ~{est_tokens:,} input tokens")

    if not yes:
        confirm = input("  Proceed? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    user_msg = USER_TEMPLATE.format(objects=objects_text)

    try:
        result = await client.generate(
            system=SYSTEM_PROMPT,
            user=user_msg,
            response_model=EdgesResponse,
        )
        llm_edges = [e.model_dump() for e in result.edges]
        console.print(f"    [green]✓[/green] {len(llm_edges)} edges from LLM")
    except Exception as e:
        console.print(f"    [red]✗[/red] Edge extraction failed: {e}")
        llm_edges = []

    # Merge with suggested edges, dedup
    all_edges = list(suggested)
    for edge in llm_edges:
        key = (edge["source_id"], edge["target_id"], edge["edge_type"])
        if key not in existing_edges:
            existing_edges.add(key)
            all_edges.append(edge)

    # Write CSV
    if all_edges:
        df = pl.DataFrame(all_edges)
        df.write_csv(project.edges_file)

    project.mark_pass_complete("edges")
    console.print(f"[green]Edges complete:[/green] {len(all_edges)} edges written")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/edges.py
git commit -m "feat(ingest): add Pass 5 — edge extraction"
```

---

### Task 14: Implement Pass 6 — bundle generation

**Files:**
- Create: `src/capability_commons/cli/ingest/bundles.py`

- [ ] **Step 1: Implement bundles.py**

Create `src/capability_commons/cli/ingest/bundles.py`:

```python
"""Pass 6: Generate six-part bundles for core topic objects via LLM."""
from __future__ import annotations

from fnmatch import fnmatch

import yaml
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import BundleOutput
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a curriculum converter. Turn the canonical object into a six-part "
    "public bundle: Hook, Primer, Guide, Reference, Worksheet, and Teach-forward kit. "
    "Keep it practical, plain-language, and beginner-safe. "
    "Do not introduce unsupported claims. Output only valid JSON."
)

USER_TEMPLATE = """Generate a six-part bundle for this knowledge object.

Bundle parts:
1. hook: A compelling 1-2 sentence pitch for why this matters
2. primer: Plain-language background (200-400 words)
3. guide: Step-by-step instructions (300-600 words)
4. reference: Quick-reference items (list of strings)
5. worksheet: Hands-on exercises (list of strings)
6. teach_forward_kit: {{three_minute_version, ten_minute_outline (list), discussion_prompts (list)}}

Canonical object:
{object}"""

BUNDLE_TYPES = {"skill_guide", "project_blueprint", "module"}


async def run_bundles(
    project: IngestProject,
    client: LLMClient,
    skip_existing: bool = False,
    slugs_filter: str | None = None,
    yes: bool = False,
) -> None:
    """Execute Pass 6: generate six-part bundles."""
    console = Console()

    draft_files = sorted(project.drafts_dir.glob("*.yaml"))
    to_process = []

    for draft_file in draft_files:
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)
        co_type = (obj.get("co_type") or obj.get("seed_type", "")).lower()

        if co_type not in BUNDLE_TYPES:
            continue
        if slugs_filter and not fnmatch(slug, slugs_filter):
            continue
        if skip_existing and obj.get("bundle_overrides"):
            continue
        to_process.append((draft_file, obj, slug))

    console.print(f"  {len(to_process)} objects for bundle generation")

    if not to_process:
        console.print("[dim]Nothing to bundle.[/dim]")
        return

    if not yes:
        confirm = input("  Proceed? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    bundled = 0
    for draft_file, obj, slug in to_process:
        user_msg = USER_TEMPLATE.format(
            object=yaml.dump(obj, default_flow_style=False),
        )

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=BundleOutput,
            )
            obj["bundle_overrides"] = result.model_dump()
            with open(draft_file, "w") as f:
                yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            bundled += 1
            console.print(f"    [green]✓[/green] {slug}")
        except Exception as e:
            console.print(f"    [red]✗[/red] {slug}: {e}")

    project.mark_pass_complete("bundles")
    console.print(f"[green]Bundles complete:[/green] {bundled} bundles generated")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/bundles.py
git commit -m "feat(ingest): add Pass 6 — bundle generation"
```

---

### Task 15: Implement Pass 7 — load to database

**Files:**
- Create: `src/capability_commons/cli/ingest/load.py`

- [ ] **Step 1: Implement load.py**

Create `src/capability_commons/cli/ingest/load.py`:

```python
"""Pass 7: Validate, write seed-compatible output, and load to database."""
from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl
import yaml
from rich.console import Console

from capability_commons.cli.ingest.project import IngestProject
from capability_commons.cli.ingest.validate import print_validation_report, run_validate


def write_seed_output(project: IngestProject) -> int:
    """Write drafts + edges into seed-compatible output/ directory."""
    output_nodes = project.output_dir / "canonical" / "nodes"
    output_edges = project.output_dir / "imports"
    output_nodes.mkdir(parents=True, exist_ok=True)
    output_edges.mkdir(parents=True, exist_ok=True)

    # Copy draft YAML files to output
    count = 0
    for draft_file in sorted(project.drafts_dir.glob("*.yaml")):
        shutil.copy2(draft_file, output_nodes / draft_file.name)
        count += 1

    # Copy edges CSV
    if project.edges_file.exists():
        shutil.copy2(project.edges_file, output_edges / "edges.csv")

    return count


async def run_load(
    project: IngestProject,
    db_url: str | None = None,
    publish: bool = False,
    dry_run: bool = False,
) -> None:
    """Execute Pass 7: validate, write output, optionally load to DB."""
    console = Console()

    # Step 1: Validate
    console.print("[bold]Validating...[/bold]")
    report = run_validate(project)
    print_validation_report(report, console)

    if report.errors:
        console.print("\n[red bold]Cannot load: fix errors first.[/red bold]")
        return

    # Step 2: If publishing, patch lifecycle_state in drafts
    if publish:
        console.print("\n[bold]Setting lifecycle_state=PUBLISHED...[/bold]")
        for draft_file in sorted(project.drafts_dir.glob("*.yaml")):
            with open(draft_file) as f:
                obj = yaml.safe_load(f)
            obj["lifecycle_state"] = "PUBLISHED"
            with open(draft_file, "w") as f:
                yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Step 3: Write seed-compatible output
    console.print("\n[bold]Writing seed-compatible output...[/bold]")
    count = write_seed_output(project)
    console.print(f"  {count} objects → output/canonical/nodes/")

    if dry_run:
        console.print("\n[yellow]Dry run — skipping database load.[/yellow]")
        return

    # Step 4: Load via seed.py
    console.print("\n[bold]Loading to database...[/bold]")
    from capability_commons.cli.seed import seed_graph

    if db_url is None:
        from capability_commons.config import get_settings
        db_url = get_settings().database_url

    await seed_graph(project.output_dir, db_url)

    project.mark_pass_complete("load")
    console.print("[green bold]Load complete.[/green bold]")
```

- [ ] **Step 2: Commit**

```bash
git add src/capability_commons/cli/ingest/load.py
git commit -m "feat(ingest): add Pass 7 — validate, output, and load to database"
```

---

## Chunk 4: CLI Dispatch & Documentation

### Task 16: Implement CLI dispatch (`__main__.py`)

**Files:**
- Create: `src/capability_commons/cli/ingest/__main__.py`

- [ ] **Step 1: Implement __main__.py**

Create `src/capability_commons/cli/ingest/__main__.py`:

```python
"""CLI entry point: python -m capability_commons.cli.ingest <command> <project>."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[4] / "ingestion" / "projects"


def get_llm_client(args, manifest_llm=None):
    """Build LLMClient from CLI args + manifest config."""
    from capability_commons.cli.ingest.llm_client import LLMClient

    llm = manifest_llm or {}

    def _pick(attr, fallback_attr, default):
        """Pick CLI arg if not None, else manifest value, else default."""
        val = getattr(args, attr, None)
        if val is not None:
            return val
        return getattr(llm, fallback_attr, default) if hasattr(llm, fallback_attr) else default

    return LLMClient(
        base_url=_pick("base_url", "base_url", "https://api.openai.com/v1"),
        api_key=getattr(args, "api_key", None),
        model=_pick("model", "model", "gpt-4o"),
        temperature=_pick("temperature", "temperature", 0.2),
    )


def add_llm_args(parser):
    """Add common LLM override flags to a subparser."""
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--base-url", help="Override LLM API base URL")
    parser.add_argument("--api-key", help="Override API key")
    parser.add_argument("--temperature", type=float, help="Override temperature")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")


def cmd_init(args):
    from capability_commons.cli.ingest.project import IngestProject
    sources = [{
        "id": args.source_id,
        "file": f"sources/{Path(args.source).name}",
        "title": args.source_title,
        "source_kind": args.source_kind,
    }]
    proj = IngestProject.init(PROJECTS_ROOT, args.project, sources)
    # Copy source file
    import shutil
    dest = proj.root / "sources" / Path(args.source).name
    shutil.copy2(args.source, dest)
    print(f"Project initialized: {proj.root}")


def cmd_parse(args):
    from capability_commons.cli.ingest.parse import run_parse
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    run_parse(proj)


def cmd_extract(args):
    from capability_commons.cli.ingest.extract import run_extract
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_extract(proj, client, sections_filter=args.sections, yes=args.yes))


def cmd_draft(args):
    from capability_commons.cli.ingest.draft import run_draft
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_draft(proj, client, skip_existing=args.skip_existing, slugs_filter=args.slugs, yes=args.yes))


def cmd_cite(args):
    from capability_commons.cli.ingest.cite import run_cite
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_cite(proj, client, slugs_filter=args.slugs, yes=args.yes))


def cmd_canonicalize(args):
    from capability_commons.cli.ingest.canonicalize import run_canonicalize
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_canonicalize(proj, client, yes=args.yes))


def cmd_edges(args):
    from capability_commons.cli.ingest.edges import run_edges
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_edges(proj, client, yes=args.yes))


def cmd_bundles(args):
    from capability_commons.cli.ingest.bundles import run_bundles
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    client = get_llm_client(args, proj.manifest.llm)
    asyncio.run(run_bundles(proj, client, skip_existing=args.skip_existing, slugs_filter=args.slugs, yes=args.yes))


def cmd_load(args):
    from capability_commons.cli.ingest.load import run_load
    from capability_commons.cli.ingest.project import IngestProject
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    asyncio.run(run_load(proj, db_url=args.db_url, publish=args.publish, dry_run=args.dry_run))


def cmd_validate(args):
    from capability_commons.cli.ingest.project import IngestProject
    from capability_commons.cli.ingest.validate import print_validation_report, run_validate
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    report = run_validate(proj)
    print_validation_report(report)
    sys.exit(1 if report.errors else 0)


def cmd_status(args):
    from capability_commons.cli.ingest.project import IngestProject
    from capability_commons.cli.ingest.validate import run_status
    proj = IngestProject.load(PROJECTS_ROOT, args.project)
    run_status(proj)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m capability_commons.cli.ingest",
        description="Capability Commons ingestion pipeline — convert source documents into knowledge objects.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # init
    p = subs.add_parser("init", help="Initialize a new ingestion project")
    p.add_argument("project", help="Project name")
    p.add_argument("--source", required=True, help="Path to source PDF")
    p.add_argument("--source-id", required=True, help="Evidence source ID (e.g., src.permatil.refbook.2006)")
    p.add_argument("--source-title", required=True, help="Source document title")
    p.add_argument("--source-kind", default="BOOK", help="Source kind (BOOK, FILE, STANDARD, etc.)")
    p.set_defaults(func=cmd_init)

    # parse
    p = subs.add_parser("parse", help="Pass 0: Parse PDFs into segments")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_parse)

    # extract
    p = subs.add_parser("extract", help="Pass 1: Generate extraction matrix from segments")
    p.add_argument("project", help="Project name")
    p.add_argument("--sections", help="Filter to sections matching this string")
    add_llm_args(p)
    p.set_defaults(func=cmd_extract)

    # draft
    p = subs.add_parser("draft", help="Pass 2: Draft canonical YAML objects")
    p.add_argument("project", help="Project name")
    p.add_argument("--skip-existing", action="store_true", help="Skip slugs that already have draft files")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_draft)

    # cite
    p = subs.add_parser("cite", help="Pass 3: Link citations to source spans")
    p.add_argument("project", help="Project name")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_cite)

    # canonicalize
    p = subs.add_parser("canonicalize", help="Pass 4: Deduplicate and canonicalize drafts")
    p.add_argument("project", help="Project name")
    add_llm_args(p)
    p.set_defaults(func=cmd_canonicalize)

    # edges
    p = subs.add_parser("edges", help="Pass 5: Extract edges from object set")
    p.add_argument("project", help="Project name")
    add_llm_args(p)
    p.set_defaults(func=cmd_edges)

    # bundles
    p = subs.add_parser("bundles", help="Pass 6: Generate six-part bundles")
    p.add_argument("project", help="Project name")
    p.add_argument("--skip-existing", action="store_true", help="Skip objects that already have bundles")
    p.add_argument("--slugs", help="Filter to slugs matching this glob pattern")
    add_llm_args(p)
    p.set_defaults(func=cmd_bundles)

    # load
    p = subs.add_parser("load", help="Pass 7: Validate and load to database")
    p.add_argument("project", help="Project name")
    p.add_argument("--publish", action="store_true", help="Set lifecycle_state to PUBLISHED")
    p.add_argument("--dry-run", action="store_true", help="Validate and write output only, no DB")
    p.add_argument("--db-url", help="Database URL (default: from .env)")
    p.set_defaults(func=cmd_load)

    # validate
    p = subs.add_parser("validate", help="Validate drafts and edges")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_validate)

    # status
    p = subs.add_parser("status", help="Show project status")
    p.add_argument("project", help="Project name")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help works**

Run: `cd ~/Projects/CapabilityCommons && python -m capability_commons.cli.ingest --help`
Expected: Shows usage with all subcommands listed.

Run: `python -m capability_commons.cli.ingest init --help`
Expected: Shows init command help with all flags.

- [ ] **Step 3: Commit**

```bash
git add src/capability_commons/cli/ingest/__main__.py
git commit -m "feat(ingest): add CLI dispatch with all commands"
```

---

### Task 17: Write LLM pass unit tests with mocked responses

**Files:**
- Create: `tests/test_ingest_passes.py`
- Create: `tests/fixtures/ingest/` (fixture files)

- [ ] **Step 1: Create test fixtures directory**

```bash
mkdir -p ~/Projects/CapabilityCommons/tests/fixtures/ingest
```

- [ ] **Step 2: Write pass tests with mocked LLM**

Create `tests/test_ingest_passes.py`:

```python
"""Tests for LLM passes with mocked responses."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import orjson
import pytest
import yaml

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject


@pytest.fixture
def project_with_segments(tmp_path):
    """Create a project with pre-generated segments."""
    proj = IngestProject.init(
        projects_root=tmp_path / "projects",
        name="test-passes",
        sources=[{
            "id": "src.test",
            "file": "sources/test.pdf",
            "title": "Test Book",
            "source_kind": "BOOK",
        }],
    )
    # Write segments
    segments = [
        SourceSegment(
            source_id="src.test",
            segment_id="seg_000001",
            page_start=1,
            page_end=1,
            heading_path=["Chapter 1", "Water Storage"],
            text="Water should be stored in food-grade containers for at least 72 hours.",
            start_char=0,
            end_char=70,
        ),
        SourceSegment(
            source_id="src.test",
            segment_id="seg_000002",
            page_start=2,
            page_end=2,
            heading_path=["Chapter 1", "Treatment"],
            text="Treat water with chlorine or boiling before long-term storage.",
            start_char=71,
            end_char=131,
        ),
    ]
    with open(proj.segments_file, "wb") as f:
        for seg in segments:
            f.write(orjson.dumps(seg.model_dump()) + b"\n")
    proj.mark_pass_complete("parse")
    return proj


class TestExtractPass:
    async def test_writes_matrix_csv(self, project_with_segments):
        from capability_commons.cli.ingest.extract import run_extract
        from capability_commons.cli.ingest.llm_client import LLMClient

        mock_llm_response = {
            "rows": [{
                "source_id": "src.test",
                "section_id": "sec_001",
                "start_page": 1,
                "end_page": 1,
                "heading_path": "Chapter 1 > Water Storage",
                "segment_ids": ["seg_000001"],
                "candidate_slug": "water.safe-storage",
                "candidate_type": "skill_guide",
                "primary_domain": "water",
                "stage": "household",
                "summary": "How to store water safely.",
                "confidence": 0.9,
            }]
        }

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content=json.dumps(mock_llm_response)))
        ]

        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
            await run_extract(project_with_segments, client, yes=True)

        assert project_with_segments.matrix_file.exists()


class TestDraftPass:
    async def test_writes_draft_yaml(self, project_with_segments):
        from capability_commons.cli.ingest.draft import run_draft
        from capability_commons.cli.ingest.llm_client import LLMClient

        # First create a matrix
        import polars as pl
        matrix_data = [{
            "source_id": "src.test",
            "section_id": "sec_001",
            "start_page": 1,
            "end_page": 1,
            "heading_path": "Chapter 1 > Water Storage",
            "segment_ids": "seg_000001",
            "candidate_slug": "water.safe-storage",
            "candidate_type": "skill_guide",
            "primary_domain": "water",
            "stage": "household",
            "summary": "How to store water safely.",
            "confidence": 0.9,
        }]
        pl.DataFrame(matrix_data).write_csv(project_with_segments.matrix_file)

        mock_llm_response = {
            "id": "water.safe-storage",
            "slug": "water.safe-storage",
            "canonical_title": "Emergency Water Storage",
            "markdown_body": "# What this is\nHow to store water safely.",
            "co_type": "SKILL_GUIDE",
        }

        client = LLMClient(base_url="https://test", api_key="test", model="test")
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(message=AsyncMock(content=json.dumps(mock_llm_response)))
        ]

        with patch.object(client._client.chat.completions, "create", return_value=mock_response):
            await run_draft(project_with_segments, client, yes=True)

        draft_file = project_with_segments.drafts_dir / "water.safe-storage.yaml"
        assert draft_file.exists()
        obj = yaml.safe_load(draft_file.read_text())
        assert obj["canonical_title"] == "Emergency Water Storage"
```

- [ ] **Step 3: Run tests**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/test_ingest_passes.py -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ingest_passes.py tests/fixtures/ingest/
git commit -m "test(ingest): add unit tests for LLM passes with mocked responses"
```

---

### Task 18: Rewrite ingestion README as operator guide

**Files:**
- Modify: `ingestion/README.md`

- [ ] **Step 1: Replace ingestion/README.md with operator guide**

Rewrite `ingestion/README.md` with:
- Prerequisites and installation section
- Quick start walkthrough (init → parse → extract → ... → load)
- Project directory reference
- Manifest configuration reference
- Per-pass documentation (what it does, what to review, common issues)
- How to scope a pilot run with `--sections` and `--slugs`
- Cost estimation guidance
- Troubleshooting section
- Reference to the detailed corpus_conversion_guide.md for methodology

- [ ] **Step 2: Commit**

```bash
git add ingestion/README.md
git commit -m "docs: rewrite ingestion README as practical operator guide"
```

---

### Task 19: Final integration verification

- [ ] **Step 1: Run all tests**

Run: `cd ~/Projects/CapabilityCommons && python -m pytest tests/ -v`
Expected: All tests pass, including existing tests (backwards compatibility).

- [ ] **Step 2: Verify CLI end-to-end**

```bash
# Test init
python -m capability_commons.cli.ingest init test-verify \
  --source tests/fixtures/ingest/test.pdf \
  --source-id src.test \
  --source-title "Test" \
  --source-kind BOOK

# Test status
python -m capability_commons.cli.ingest status test-verify

# Test validate (should warn about no drafts)
python -m capability_commons.cli.ingest validate test-verify
```

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "feat(ingest): complete ingestion pipeline CLI with all passes"
```
