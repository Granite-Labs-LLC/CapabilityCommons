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
