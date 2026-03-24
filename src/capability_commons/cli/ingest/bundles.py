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
