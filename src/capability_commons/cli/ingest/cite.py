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
    # Adjacent segments included as bounded context for citations. Wider than
    # 1 because the extraction matrix often assigns a single segment per row
    # while the supporting passage spans the section around it.
    NEIGHBOR_WINDOW = 3

    for draft_file in draft_files:
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)

        # Scope strictly to the object's extracted source segments. Without
        # them we cannot honestly cite — skip rather than fabricate support
        # from arbitrary segments of the source.
        source_seg_ids = {
            sid for sid in obj.get("source_segment_ids", []) if sid in segments_by_id
        }
        if not source_seg_ids:
            console.print(
                f"    [yellow]⚠[/yellow] {slug}: no source_segment_ids — skipping"
            )
            continue

        primary_segs = [segments_by_id[sid] for sid in source_seg_ids]

        # Bounded neighbor context, restricted to the source(s) the primary
        # segments came from. We do NOT fall back to project.sources[0].
        primary_source_ids = {s.source_id for s in primary_segs}
        relevant: dict[str, SourceSegment] = {s.segment_id: s for s in primary_segs}
        for src_id in primary_source_ids:
            ordered = sorted(
                (s for s in segments_by_id.values() if s.source_id == src_id),
                key=lambda s: s.start_char,
            )
            id_to_idx = {s.segment_id: i for i, s in enumerate(ordered)}
            for seg in primary_segs:
                if seg.source_id != src_id:
                    continue
                idx = id_to_idx[seg.segment_id]
                for offset in range(-NEIGHBOR_WINDOW, NEIGHBOR_WINDOW + 1):
                    ni = idx + offset
                    if 0 <= ni < len(ordered):
                        relevant.setdefault(ordered[ni].segment_id, ordered[ni])

        relevant_segs = list(relevant.values())
        allowed_seg_ids = set(relevant)
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

            # Drop citations whose support points outside the allowed
            # segment set; the LLM occasionally invents segment IDs or
            # returns the short form without the "<source_id>::" prefix.
            allowed_short = {
                sid.split("::", 1)[1]: sid for sid in allowed_seg_ids if "::" in sid
            }

            def _normalize_segment_id(sid: str) -> str | None:
                if sid in allowed_seg_ids:
                    return sid
                return allowed_short.get(sid)

            kept: list[ClaimCitation] = []
            dropped = 0
            for claim in result.citations:
                clean_support = []
                for span in claim.support:
                    norm = _normalize_segment_id(span.segment_id)
                    if norm is None:
                        continue
                    clean_support.append(
                        span if norm == span.segment_id
                        else span.model_copy(update={"segment_id": norm})
                    )
                if not clean_support:
                    dropped += 1
                    continue
                kept.append(claim.model_copy(update={"support": clean_support}))

            obj["citations"] = [c.model_dump() for c in kept]
            with open(draft_file, "w") as f:
                yaml.dump(obj, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            all_citations.extend(c.model_dump() for c in kept)
            suffix = f" ({dropped} unsupported dropped)" if dropped else ""
            console.print(
                f"    [green]✓[/green] {slug}: {len(kept)} citations{suffix}"
            )
        except Exception as e:
            console.print(f"    [red]✗[/red] {slug}: {e}")

    # Write evidence map
    with open(project.evidence_map_file, "wb") as f:
        f.write(orjson.dumps(all_citations, option=orjson.OPT_INDENT_2))

    project.mark_pass_complete("cite")
    console.print(f"[green]Cite complete:[/green] {len(all_citations)} citations linked")
