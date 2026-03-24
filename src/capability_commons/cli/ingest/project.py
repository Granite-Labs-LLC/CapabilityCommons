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
