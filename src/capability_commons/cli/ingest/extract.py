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
            if df[col].dtype.base_type() == pl.List:
                df = df.with_columns(
                    pl.col(col).cast(pl.List(pl.Utf8)).list.join("|").alias(col)
                )
        df.write_csv(project.matrix_file)

    project.mark_pass_complete("extract")
    console.print(f"[green]Extract complete:[/green] {len(all_rows)} rows written")
