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
