"""Pass 7: Validate, write seed-compatible output, and load to database."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from rich.console import Console

from capability_commons.cli.ingest.project import IngestProject
from capability_commons.cli.ingest.validate import print_validation_report, run_validate


def _patch_lifecycle(drafts_dir: Path) -> None:
    """Set lifecycle_state to canonical lowercase 'published' on all drafts."""
    for draft_file in sorted(drafts_dir.glob("*.yaml")):
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        obj["lifecycle_state"] = "published"
        with open(draft_file, "w") as f:
            yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


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
        console.print("\n[bold]Setting lifecycle_state=published...[/bold]")
        _patch_lifecycle(project.drafts_dir)

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
