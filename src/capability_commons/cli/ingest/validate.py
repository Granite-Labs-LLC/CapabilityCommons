"""Validate and status commands for ingestion projects."""
from __future__ import annotations

from pathlib import Path

import orjson
import yaml
from rich.console import Console
from rich.table import Table

from capability_commons.cli.ingest.canonical_schema import VALID_CO_TYPES
from capability_commons.cli.ingest.models import ValidationReport
from capability_commons.cli.ingest.project import IngestProject
from capability_commons.domain.enums import EdgeType

# Valid enum values from domain/enums.py
VALID_STAGES = {"foundation", "household", "productive", "community", "advanced"}
VALID_COST_BANDS = {"free", "low", "medium", "high"}
VALID_RISK_BANDS = {"low", "moderate", "high", "expert_only"}
VALID_LIFECYCLE = {"draft", "in_review", "reviewed", "verified", "published", "deprecated", "archived"}
VALID_EDGE_TYPES = {e.value for e in EdgeType}

# Minimum citation coverage threshold (fraction of objects that must have citations)
MIN_CITATION_COVERAGE = 0.5

# Type-specific required structured_data fields
STRUCTURED_DATA_REQUIRED: dict[str, list[str]] = {
    "skill_guide": ["tools", "materials"],
    "project_blueprint": ["phases"],
    "assessment": ["assessment_type"],
}

# PLAN P1-8 publish-gate constants.
ACTIONABLE_TYPES = {"skill_guide", "project_blueprint"}
MIN_CITATIONS_PER_PUBLISHED_OBJECT = 2
ENVELOPE_REQUIRED_FIELDS = (
    "smallest_viable_version",
    "stop_conditions",
    "success_checks",
)


def _check_publish_gate(obj: dict, slug: str, lifecycle: str) -> list[str]:
    """Run the strict publish-readiness checks for a single draft and return
    a list of blocker descriptions. Empty list = ready to publish."""
    if lifecycle != "published":
        return []
    blockers: list[str] = []
    co_type = (obj.get("co_type") or obj.get("candidate_type") or "").lower().replace(" ", "_")

    # 1. Citation precision: every published object needs ≥2 citations.
    n_citations = len(obj.get("citations") or [])
    if n_citations < MIN_CITATIONS_PER_PUBLISHED_OBJECT:
        blockers.append(
            f"{slug}: published objects need at least "
            f"{MIN_CITATIONS_PER_PUBLISHED_OBJECT} citations (has {n_citations})"
        )

    # 2. Implementation envelope required for actionable types.
    if co_type in ACTIONABLE_TYPES:
        envelope = (obj.get("structured_data") or {}).get("implementation")
        if not envelope:
            blockers.append(
                f"{slug}: {co_type} requires structured_data.implementation envelope"
            )
        else:
            missing = [
                f for f in ENVELOPE_REQUIRED_FIELDS if not envelope.get(f)
            ]
            if missing:
                blockers.append(
                    f"{slug}: implementation envelope missing: {', '.join(missing)}"
                )

    # 3. Safety review for high-risk content.
    risk = obj.get("risk_band", "")
    if risk in ("high", "expert_only"):
        sd = obj.get("structured_data") or {}
        safety = sd.get("safety_boundary") or sd.get("safety_review")
        if not safety:
            blockers.append(
                f"{slug}: risk_band={risk} requires structured_data.safety_boundary "
                "(or safety_review note) before publish"
            )

    return blockers


def run_validate(project: IngestProject, *, strict: bool = False) -> ValidationReport:
    """Validate all drafts and edges in a project.

    This is the release gate for ingest output. Errors block loading;
    warnings are advisory.

    When `strict=True`, additional publish-gate checks run (PLAN P1-8):
    every object with lifecycle_state=='published' must have ≥2 citations,
    actionable types (skill_guide/project_blueprint) must carry an
    implementation envelope, and high-risk content must have a safety
    review note. Violations populate `publish_blockers` and are also
    surfaced through `errors`.
    """
    errors: list[str] = []
    warnings: list[str] = []
    publish_blockers: list[str] = []

    # Load segments for cross-referencing
    segment_ids: set[str] = set()
    if project.segments_file.exists():
        for line in project.segments_file.read_text().strip().splitlines():
            seg = orjson.loads(line)
            segment_ids.add(seg.get("segment_id", ""))

    # Load drafts
    drafts_dir = project.drafts_dir
    draft_files = sorted(drafts_dir.glob("*.yaml"))
    draft_slugs: set[str] = set()
    slug_files: dict[str, list[str]] = {}
    objects_with_citations = 0
    total_citations = 0

    for draft_file in draft_files:
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)

        # Duplicate slug detection
        slug_files.setdefault(slug, []).append(draft_file.name)
        draft_slugs.add(slug)

        # Required fields
        if not obj.get("canonical_title") and not obj.get("title"):
            errors.append(f"{slug}: missing title/canonical_title")
        if not obj.get("markdown_body"):
            errors.append(f"{slug}: missing markdown_body")

        # co_type is required
        co_type = obj.get("co_type", obj.get("candidate_type", ""))
        if not co_type:
            errors.append(f"{slug}: missing co_type")
        elif co_type.lower().replace(" ", "_") not in VALID_CO_TYPES:
            errors.append(f"{slug}: invalid co_type '{co_type}'")

        # plain_language is required for publication
        if not obj.get("plain_language"):
            errors.append(f"{slug}: missing plain_language (required)")

        # Valid enum values
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

        # Type-specific structured_data validation
        co_type_norm = co_type.lower().replace(" ", "_") if co_type else ""
        sd = obj.get("structured_data") or {}
        required_fields = STRUCTURED_DATA_REQUIRED.get(co_type_norm, [])
        for field in required_fields:
            if field not in sd:
                warnings.append(f"{slug}: structured_data missing '{field}' (expected for {co_type_norm})")

        # Citation coverage
        citations = obj.get("citations", [])
        if citations:
            objects_with_citations += 1
            total_citations += len(citations)
            # Validate citation structure. The canonical post-cite-pass shape
            # nests source_id inside each support[] span (ClaimCitation), but
            # legacy seed CSV cites carry source_id at the top level. Accept
            # either form; warn only when neither is present.
            for i, cit in enumerate(citations):
                support = cit.get("support") or cit.get("spans") or []
                top_source = cit.get("source_id")
                if not top_source and not any(s.get("source_id") for s in support):
                    warnings.append(f"{slug}: citation[{i}] missing source_id")
                for span in support:
                    if not span.get("excerpt"):
                        warnings.append(f"{slug}: citation[{i}] has span without excerpt")
        else:
            warnings.append(f"{slug}: no citations")

        # Source segment reference validation
        source_seg_ids = obj.get("source_segment_ids", [])
        if source_seg_ids and segment_ids:
            for sid in source_seg_ids:
                if sid not in segment_ids:
                    warnings.append(f"{slug}: references unknown segment '{sid}'")

        # Safety checks
        failure_modes = sd.get("failure_modes") or obj.get("payload", {}).get("failure_modes")
        if failure_modes and not risk:
            warnings.append(f"{slug}: has failure_modes but no risk_band")
        if risk in ("high", "expert_only"):
            safety = sd.get("safety_boundary") or obj.get("payload", {}).get("safety_boundary")
            if not safety:
                errors.append(f"{slug}: risk_band={risk} requires safety_boundary")

        # Strict publish-gate checks (PLAN P1-8)
        if strict:
            publish_blockers.extend(_check_publish_gate(obj, slug, lifecycle))

    # Duplicate slugs are errors
    for slug, files in slug_files.items():
        if len(files) > 1:
            errors.append(f"Duplicate slug '{slug}' in: {', '.join(files)}")

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
            edge_type = row.get("edge_type", "")
            if edge_type and edge_type.lower() not in VALID_EDGE_TYPES:
                errors.append(f"Edge '{row['source_id']}->{row['target_id']}': invalid edge_type '{edge_type}'")

    objects_count = len(draft_files)
    coverage = objects_with_citations / objects_count if objects_count > 0 else 0.0

    # Citation coverage threshold
    if objects_count > 0 and coverage < MIN_CITATION_COVERAGE:
        warnings.append(
            f"Citation coverage {coverage:.0%} is below minimum threshold {MIN_CITATION_COVERAGE:.0%}"
        )

    # Surface publish-gate blockers as errors so the load step refuses to ship
    # broken content. Keep them in `publish_blockers` too for granular UI.
    if strict and publish_blockers:
        errors.extend(publish_blockers)

    return ValidationReport(
        objects_count=objects_count,
        edges_count=edges_count,
        citations_count=total_citations,
        errors=errors,
        warnings=warnings,
        citation_coverage=coverage,
        publish_blockers=publish_blockers,
    )


def print_validation_report(report: ValidationReport, console: Console | None = None) -> None:
    """Print a formatted validation report."""
    console = console or Console()

    console.print(f"\n[bold]Validation Report[/bold]")
    console.print(f"  Objects: {report.objects_count}")
    console.print(f"  Edges: {report.edges_count}")
    console.print(f"  Citations: {report.citations_count}")
    console.print(f"  Citation coverage: {report.citation_coverage:.0%}")

    if report.publish_blockers:
        console.print(
            f"\n[red bold]Publish blockers ({len(report.publish_blockers)}):[/red bold]"
        )
        for b in report.publish_blockers:
            console.print(f"  [red]✗[/red] {b}")

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
