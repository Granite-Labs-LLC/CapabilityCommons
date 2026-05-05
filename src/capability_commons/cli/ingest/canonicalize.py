"""Pass 4: Canonicalize and deduplicate drafts via LLM + fuzzy matching."""
from __future__ import annotations

import shutil

import orjson
import yaml
from pydantic import BaseModel
from rapidfuzz import fuzz
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import CanonicalizationDecision
from capability_commons.cli.ingest.project import IngestProject

SYSTEM_PROMPT = (
    "You are a corpus editor. Merge duplicates and split overloaded drafts "
    "while preserving provenance. Choose one canonical slug. Do not discard "
    "source support. Output only valid JSON."
)

USER_TEMPLATE = """These drafts appear similar. For each group, decide:
- "keep": both are distinct, no changes needed
- "merge": combine into one canonical object. Include the full merged object as "merged_object".
- "split": one object should be split into multiple. Include the split objects as "split_objects".

Return a JSON object with key "decisions" containing an array of decisions.
Each decision: {{action, rationale, canonical_slug, deprecated_draft_ids, merged_object (if merge), split_objects (if split)}}

Draft set:
{drafts}"""

SIMILARITY_THRESHOLD = 75  # rapidfuzz ratio threshold


class CanonicalizeResponse(BaseModel):
    decisions: list[CanonicalizationDecision]


def find_similar_groups(
    drafts: dict[str, dict],
    threshold: int = SIMILARITY_THRESHOLD,
) -> list[list[str]]:
    """Group drafts by title/summary similarity using rapidfuzz."""
    slugs = list(drafts.keys())
    visited: set[str] = set()
    groups: list[list[str]] = []

    for i, slug_a in enumerate(slugs):
        if slug_a in visited:
            continue
        group = [slug_a]
        title_a = drafts[slug_a].get("canonical_title", "")
        summary_a = drafts[slug_a].get("summary_short", "")
        domain_a = drafts[slug_a].get("primary_domain", "")

        for slug_b in slugs[i + 1:]:
            if slug_b in visited:
                continue
            domain_b = drafts[slug_b].get("primary_domain", "")
            if domain_a != domain_b:
                continue
            title_b = drafts[slug_b].get("canonical_title", "")
            summary_b = drafts[slug_b].get("summary_short", "")
            title_sim = fuzz.ratio(title_a, title_b)
            summary_sim = fuzz.ratio(summary_a, summary_b)
            if max(title_sim, summary_sim) >= threshold:
                group.append(slug_b)
                visited.add(slug_b)

        if len(group) > 1:
            groups.append(group)
        visited.add(slug_a)

    return groups


def _merge_lineage(originals: list[dict]) -> tuple[list[str], list[dict]]:
    """Combine source_segment_ids and citations from a set of source drafts."""
    seg_ids: list[str] = []
    seen_segs: set[str] = set()
    for orig in originals:
        for sid in orig.get("source_segment_ids") or []:
            if sid not in seen_segs:
                seen_segs.add(sid)
                seg_ids.append(sid)
    citations: list[dict] = []
    for orig in originals:
        citations.extend(orig.get("citations") or [])
    return seg_ids, citations


def _apply_merge(decision, drafts, project, merged_dir, console) -> None:
    if not decision.merged_object:
        console.print(
            f"    [red]merge skipped[/red] {decision.canonical_slug}: "
            "no merged_object returned"
        )
        return
    if not decision.deprecated_draft_ids:
        console.print(
            f"    [red]merge skipped[/red] {decision.canonical_slug}: "
            "no deprecated_draft_ids"
        )
        return

    merged = dict(decision.merged_object)
    merged.setdefault("slug", decision.canonical_slug)
    merged.setdefault("id", decision.canonical_slug)

    originals = [drafts[d] for d in decision.deprecated_draft_ids if d in drafts]
    seg_ids, citations = _merge_lineage(originals)
    merged.setdefault("source_segment_ids", seg_ids)
    if not merged.get("citations"):
        merged["citations"] = citations

    # Write the canonical replacement BEFORE moving deprecated drafts so a
    # canonical_slug that matches a deprecated id is not first archived and
    # then re-created out of order.
    merged_path = project.drafts_dir / f"{decision.canonical_slug}.yaml"
    with open(merged_path, "w") as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    for dep_id in decision.deprecated_draft_ids:
        if dep_id == decision.canonical_slug:
            continue  # canonical was just (re)written; do not archive it
        src = project.drafts_dir / f"{dep_id}.yaml"
        if src.exists():
            shutil.move(str(src), str(merged_dir / src.name))

    console.print(
        f"    [green]merge[/green] -> {decision.canonical_slug} "
        f"(deprecated: {decision.deprecated_draft_ids})"
    )


def _apply_split(decision, drafts, project, split_dir, console) -> None:
    if not decision.split_objects:
        console.print(
            f"    [red]split skipped[/red] {decision.canonical_slug}: "
            "no split_objects returned"
        )
        return
    if not decision.deprecated_draft_ids:
        console.print(
            f"    [red]split skipped[/red] {decision.canonical_slug}: "
            "no deprecated_draft_ids"
        )
        return

    parents = [drafts[d] for d in decision.deprecated_draft_ids if d in drafts]
    parent_seg_ids, parent_citations = _merge_lineage(parents)

    written: list[str] = []
    for child in decision.split_objects:
        child = dict(child)
        child_slug = child.get("slug") or child.get("id")
        if not child_slug:
            continue
        # Inherit lineage from the parent(s) when the child does not declare it.
        child.setdefault("source_segment_ids", parent_seg_ids)
        if not child.get("citations"):
            child["citations"] = parent_citations
        child_path = project.drafts_dir / f"{child_slug}.yaml"
        with open(child_path, "w") as f:
            yaml.dump(child, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        written.append(child_slug)

    for dep_id in decision.deprecated_draft_ids:
        if dep_id in written:
            continue
        src = project.drafts_dir / f"{dep_id}.yaml"
        if src.exists():
            shutil.move(str(src), str(split_dir / src.name))

    console.print(
        f"    [blue]split[/blue] {decision.canonical_slug} -> {written} "
        f"(original: {decision.deprecated_draft_ids})"
    )


async def run_canonicalize(
    project: IngestProject,
    client: LLMClient,
    yes: bool = False,
) -> None:
    """Execute Pass 4: deduplicate and canonicalize drafts."""
    console = Console()

    # Load all drafts
    drafts: dict[str, dict] = {}
    for draft_file in sorted(project.drafts_dir.glob("*.yaml")):
        with open(draft_file) as f:
            obj = yaml.safe_load(f)
        slug = obj.get("slug") or obj.get("id", draft_file.stem)
        drafts[slug] = obj

    console.print(f"  {len(drafts)} drafts loaded")

    # Find similar groups
    groups = find_similar_groups(drafts)
    console.print(f"  {len(groups)} potentially similar groups found")

    if not groups:
        console.print("[dim]No duplicates detected.[/dim]")
        project.mark_pass_complete("canonicalize")
        return

    if not yes:
        confirm = input("  Proceed with LLM review? [y/N] ")
        if confirm.lower() != "y":
            console.print("[yellow]Aborted.[/yellow]")
            return

    # Ensure subdirectories exist
    merged_dir = project.drafts_dir / "_merged"
    split_dir = project.drafts_dir / "_split"
    merged_dir.mkdir(exist_ok=True)
    split_dir.mkdir(exist_ok=True)

    all_decisions: list[dict] = []

    for group in groups:
        group_drafts = {slug: drafts[slug] for slug in group}
        drafts_text = "\n---\n".join(
            yaml.dump(obj, default_flow_style=False) for obj in group_drafts.values()
        )

        user_msg = USER_TEMPLATE.format(drafts=drafts_text)

        try:
            result = await client.generate(
                system=SYSTEM_PROMPT,
                user=user_msg,
                response_model=CanonicalizeResponse,
            )
            for decision in result.decisions:
                all_decisions.append(decision.model_dump())
                if decision.action == "merge":
                    _apply_merge(decision, drafts, project, merged_dir, console)
                elif decision.action == "split":
                    _apply_split(decision, drafts, project, split_dir, console)
                else:
                    console.print(f"    [dim]keep[/dim] {decision.canonical_slug}")
        except Exception as e:
            console.print(f"    [red]✗[/red] group {group}: {e}")

    # Write log
    log_path = project.drafts_dir / "canonicalization_log.json"
    with open(log_path, "wb") as f:
        f.write(orjson.dumps(all_decisions, option=orjson.OPT_INDENT_2))

    project.mark_pass_complete("canonicalize")
    console.print(f"[green]Canonicalize complete:[/green] {len(all_decisions)} decisions")
