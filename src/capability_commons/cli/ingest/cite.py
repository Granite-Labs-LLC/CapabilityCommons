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
