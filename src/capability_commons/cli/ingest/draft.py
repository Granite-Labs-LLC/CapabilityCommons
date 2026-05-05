"""Pass 2: Draft canonical YAML objects from extraction matrix via LLM."""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

import orjson
import polars as pl
import yaml
from pydantic import BaseModel, Field, field_validator
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject
from capability_commons.domain.enums import (
    COType,
    CostBand,
    LifecycleState,
    RiskBand,
    StageType,
    VisibilityType,
)


REQUIRED_BODY_SECTIONS = (
    "What this is",
    "Why it matters",
    "What you need",
    "How to do it",
    "Common failure modes",
)


class SuggestedEdge(BaseModel, extra="allow"):
    target_id: str
    edge_type: str


class DraftObject(BaseModel, extra="allow"):
    """Strict canonical-object schema used to validate every LLM draft.

    Required fields here mirror the schema documented in USER_TEMPLATE so that
    incomplete drafts fail validation rather than silently passing.
    """
    # Identity
    id: str
    slug: str
    seed_type: str
    co_type: COType
    canonical_title: str
    version_no: int = 1
    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    visibility: VisibilityType = VisibilityType.PUBLIC
    language_code: str = "en"

    # Classification
    primary_domain: str
    secondary_domains: list[str] = []
    stage: StageType
    contexts: list[str] = []
    difficulty: int = Field(..., ge=1, le=5)
    cost_band: CostBand
    risk_band: RiskBand

    # Summaries / body
    summary_short: str = Field(..., min_length=1)
    summary_medium: str = Field(..., min_length=1)
    plain_language: str = Field(..., min_length=1)
    markdown_body: str = Field(..., min_length=1)

    # Type-specific structured data + linkage
    structured_data: dict
    requires: list[str] = []
    suggested_edges: list[SuggestedEdge] = []
    citations: list = []

    # Lineage (filled by pipeline, not the LLM)
    source_segment_ids: list[str] = []

    @field_validator("markdown_body")
    @classmethod
    def _body_has_required_sections(cls, v: str) -> str:
        lower = v.lower()
        missing = [s for s in REQUIRED_BODY_SECTIONS if s.lower() not in lower]
        if missing:
            raise ValueError(
                "markdown_body missing required sections: " + ", ".join(missing)
            )
        return v

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
            # Attach source segment lineage
            result.source_segment_ids = [
                sid for sid in seg_ids if sid in segments_by_id
            ]
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
