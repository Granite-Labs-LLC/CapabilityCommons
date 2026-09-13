"""Pass 2: Draft canonical YAML objects from extraction matrix via LLM."""

from __future__ import annotations

from fnmatch import fnmatch

import orjson
import polars as pl
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from rich.console import Console

from capability_commons.cli.ingest.llm_client import LLMClient
from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject
from capability_commons.domain.enums import (
    CostBand,
    COType,
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

# Object types that publish actionable how-to content. PLAN P1-9 requires
# every such object to ship with a structured "can I do this now?" envelope
# so the public answer composer can produce action_now / implementation_plan
# / safety blocks without scraping markdown.
ACTIONABLE_TYPES = {COType.SKILL_GUIDE, COType.PROJECT_BLUEPRINT}


class ImplementationVariant(BaseModel, extra="allow"):
    """One contextual variant of a how-to (renter, low-budget, off-grid, …)."""

    label: str = Field(..., min_length=1)
    when: str = Field(..., min_length=1)  # plain-language scope
    notes: str | None = None


class ImplementationEnvelope(BaseModel, extra="allow"):
    """The "can I do this now?" envelope per PLAN.md retrieval P1-8 / ingest P1-9.

    Every actionable object (skill_guide, project_blueprint) must populate this
    so retrieval can surface a real action plan rather than a document blurb.
    """

    smallest_viable_version: str = Field(
        ..., min_length=1, description="The smallest thing the user can do RIGHT NOW that still helps."
    )
    tools: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    expected_time: str | None = Field(None, description="e.g. '30 minutes', '2 hours'")
    expected_cost: str | None = Field(None, description="e.g. 'free', '$5–$20'")
    success_checks: list[str] = Field(default_factory=list, description="Concrete checks that confirm it worked.")
    stop_conditions: list[str] = Field(default_factory=list, description="Hard stops: when to abort and not continue.")
    common_mistakes: list[str] = Field(default_factory=list)
    variants: list[ImplementationVariant] = Field(
        default_factory=list, description="Renter, low-budget, urban, off-grid adaptations."
    )
    when_to_escalate: list[str] = Field(
        default_factory=list, description="Conditions under which the user should call a pro."
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
            raise ValueError("markdown_body missing required sections: " + ", ".join(missing))
        return v

    @model_validator(mode="after")
    def _validate_implementation_envelope(self):
        """Actionable types must carry a structured implementation envelope
        under structured_data["implementation"] so the public answer composer
        can produce action_now / implementation_plan blocks (PLAN P1-9)."""
        if self.co_type not in ACTIONABLE_TYPES:
            return self
        envelope = (self.structured_data or {}).get("implementation")
        if envelope is None:
            raise ValueError(
                f"{self.co_type.value} requires structured_data.implementation "
                "(smallest_viable_version, tools, materials, success_checks, "
                "stop_conditions, …)"
            )
        # Validate the envelope shape; keep the parsed instance back on the
        # draft so downstream consumers see a normalized dict.
        validated = ImplementationEnvelope.model_validate(envelope)
        self.structured_data = {
            **self.structured_data,
            "implementation": validated.model_dump(),
        }
        return self

    @model_validator(mode="after")
    def _id_matches_slug(self):
        """`slug` is the one identifier the rest of the pipeline resolves by
        (seed.py, edges.py, validate.py all key on it; `id` is only a fallback
        for legacy seed CSVs that predate `slug`). The LLM drafts `id` and
        `slug` independently and sometimes gives an object a dot-namespaced
        `id` that disagrees with its own dash-only `slug` — the edges pass
        then can't tell the two apart from a genuinely different target,
        producing "Edge target not in drafts" errors for an object that
        actually exists. Force them to agree at the source instead of
        reconciling identifiers downstream."""
        self.id = self.slug
        return self


SYSTEM_PROMPT = (
    "You are a Capability Commons object drafter. Convert source material into "
    "learner-facing, plain-language canonical objects. Preserve accuracy. "
    "Do not invent unsupported steps or numbers. Do not copy long passages. "
    "Separate universal guidance from local adaptation. Output only valid JSON."
)

# Rendered into the prompt verbatim so the model sees the exact nested shape.
# Diagnosed 2026-09-13 on the USDA canning run: with only a prose description
# of the envelope, gpt-4o returned the flat skill-style keys (tools, materials,
# success_criteria, failure_modes, safety_boundary) on every attempt --
# including all 3 retries that quoted the validation error back to it -- and
# never produced structured_data.implementation. 11 of 75 USDA drafts failed
# this way. Kept as data (not prose) so tests can assert it stays a valid
# ImplementationEnvelope.
IMPLEMENTATION_EXAMPLE: dict = {
    "smallest_viable_version": "One sentence: the smallest step the user can take right now that still helps.",
    "tools": ["..."],
    "materials": ["..."],
    # Estimates the model tends to invent: 23 of 74 USDA drafts had
    # expected_time values ("2-3 hours") appearing nowhere in their source.
    "expected_time": "only if the source states it, otherwise null",
    "expected_cost": "only if the source states it, otherwise null",
    "success_checks": ["..."],
    "stop_conditions": ["..."],
    "common_mistakes": ["..."],
    "variants": [{"label": "renter", "when": "...", "notes": "..."}],
    "when_to_escalate": ["..."],
}

# Braces doubled because USER_TEMPLATE goes through str.format().
_IMPLEMENTATION_EXAMPLE_JSON = (
    orjson.dumps({"implementation": IMPLEMENTATION_EXAMPLE}, option=orjson.OPT_INDENT_2)
    .decode()
    .replace("{", "{{")
    .replace("}", "}}")
)

# Generated from the enums DraftObject validates against. The prompt used to
# say `lifecycle_state (DRAFT)` and list stage/cost_band/risk_band without
# values, so first attempts routinely came back with 'DRAFT', 'medium', or an
# invented stage and burned a retry on every object (seen 2026-09-13, USDA).
_ENUM_FIELDS = "\n".join(
    f"- {name}: one of {' | '.join(member.value for member in enum_cls)}"
    for name, enum_cls in (("stage", StageType), ("cost_band", CostBand), ("risk_band", RiskBand))
)

USER_TEMPLATE = (
    """Target object YAML schema fields (enum values are lowercase and must match exactly):
- id, seed_type, co_type, slug, canonical_title, version_no (1), lifecycle_state ("draft")
- visibility ("public"), language_code ("en"), primary_domain (string)
- secondary_domains, contexts (JSON lists of strings; [] when none)
"""
    + _ENUM_FIELDS
    + """
- difficulty (integer 1-5)
- summary_short, summary_medium, plain_language
- markdown_body (ONE markdown string, not an object, with "## " headings: What this is, Why it matters, What you need, How to do it, Common failure modes, Safety/boundary notes, Local adaptation notes)
- structured_data: a JSON object whose keys depend on co_type:
  skill_guide: tools, materials, success_criteria, failure_modes, safety_boundary, implementation
  project_blueprint: goal, deliverables, acceptance_criteria, safety_boundary, implementation
  concept_note: definition, key_questions, misconceptions
  REQUIRED for skill_guide and project_blueprint: structured_data.implementation,
  a NESTED object inside structured_data (not flat keys on structured_data).
  The draft is rejected without it. structured_data must contain:
"""
    + _IMPLEMENTATION_EXAMPLE_JSON
    + """
- requires (flat list of prerequisite slugs)
- suggested_edges (list of {{target_id, edge_type}})
- citations (empty list — will be populated in citation pass)

Candidate from extraction matrix:
{matrix_row}

Supporting source segments:
{segments}

Return a JSON object with all the fields listed above. The markdown_body should contain real explanatory content synthesized from the source segments, not just a summary."""
)


def _merge_duplicate_slug_rows(rows: list[dict]) -> list[dict]:
    """Collapse extraction-matrix rows that share a candidate_slug into one.

    Extraction can assign the same slug to adjacent segments covering one
    topic (USDA 2026-09-13: selecting-preparing-canning-fruit on seg_000065
    and seg_000066). Drafting each row separately wrote the same
    `<slug>.yaml` twice, silently keeping only the last segment's draft.
    Merge their segment_ids so a single draft sees all of the source.
    """
    merged: dict[str, dict] = {}
    for row in rows:
        slug = row["candidate_slug"]
        if slug not in merged:
            merged[slug] = dict(row)
            continue
        existing = merged[slug]
        ids = [s for s in (existing.get("segment_ids") or "").split("|") if s]
        ids += [s for s in (row.get("segment_ids") or "").split("|") if s and s not in ids]
        existing["segment_ids"] = "|".join(ids)
    return list(merged.values())


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
    for row in _merge_duplicate_slug_rows(list(df.iter_rows(named=True))):
        slug = row["candidate_slug"]
        if slugs_filter and not fnmatch(slug, slugs_filter):
            continue
        if skip_existing and (project.drafts_dir / f"{slug}.yaml").exists():
            continue
        rows_to_process.append(row)
        # Gather segment text for estimation (resolution is duplicated below
        # because _resolve_seg_ids isn't defined yet at this point).
        raw_ids = row.get("segment_ids", "").split("|") if row.get("segment_ids") else []
        src = row.get("source_id") or ""
        for sid in raw_ids:
            key = sid if sid in segments_by_id else f"{src}::{sid}"
            if key in segments_by_id:
                total_text += segments_by_id[key].text

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

    def _resolve_seg_ids(row: dict) -> list[str]:
        """Matrix CSV stores bare segment ids (`seg_000018`) but the segments
        store keys them as `<source_id>::seg_000018`. Resolve both forms."""
        raw = (row.get("segment_ids") or "").split("|") if row.get("segment_ids") else []
        source_id = row.get("source_id") or ""
        resolved: list[str] = []
        for sid in raw:
            if not sid:
                continue
            if sid in segments_by_id:
                resolved.append(sid)
            elif f"{source_id}::{sid}" in segments_by_id:
                resolved.append(f"{source_id}::{sid}")
        return resolved

    drafted = 0
    for row in rows_to_process:
        slug = row["candidate_slug"]
        seg_ids = _resolve_seg_ids(row)
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
            result.source_segment_ids = [sid for sid in seg_ids if sid in segments_by_id]
            # Write as YAML
            draft_path = project.drafts_dir / f"{slug}.yaml"
            with open(draft_path, "w") as f:
                yaml.safe_dump(
                    result.model_dump(mode="json"),
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            drafted += 1
            console.print(f"    [green]✓[/green] {slug}")
        except Exception as e:
            console.print(f"    [red]✗[/red] {slug}: {e}")
            # The exception only says what was missing, not what the model
            # produced instead -- keep its last raw output for diagnosis.
            last_response = getattr(e, "last_response", None)
            if last_response:
                failed_path = project.drafts_dir.parent / "logs" / f"draft-failed.{slug}.json"
                failed_path.parent.mkdir(exist_ok=True)
                failed_path.write_text(last_response)

    project.mark_pass_complete("draft")
    console.print(f"[green]Draft complete:[/green] {drafted} objects written")
