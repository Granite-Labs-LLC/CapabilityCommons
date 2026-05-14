"""Normalize LLM-produced enum values in draft YAMLs to canonical schema.

The Pass 2 (draft) LLM occasionally emits enum values that are close-but-not-exact
matches for the canonical schema. Rather than re-run the LLM, this script remaps
known synonyms to valid values.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

CO_TYPE_MAP = {
    "concept": "concept_note",
    "skill": "skill_guide",
    "project": "project_blueprint",
    "reference": "reference_sheet",
}

STAGE_MAP = {
    "skill": "productive",
    "practice": "productive",
    "deployment": "advanced",
    "analysis": "foundation",
    "concept": "foundation",
    "overview": "foundation",
    "reference": "foundation",
}

RISK_MAP = {
    "medium": "moderate",
}

COST_MAP = {
    "unknown": "free",
}

EDGE_TYPE_MAP = {
    "requires": "prerequisite_for",
    "related_to": "builds_on",
    "related": "builds_on",
}

LIFECYCLE_MAP = {
    "DRAFT": "draft",
    "REVIEW": "in_review",
    "REVIEWED": "reviewed",
    "PUBLISHED": "published",
}

DEFAULT_SAFETY_BOUNDARY = (
    "Educational/informational only — not personalized financial, legal, or "
    "operational advice. Verify with qualified professionals before acting."
)


def normalize_file(path: Path) -> tuple[bool, list[str]]:
    obj = yaml.safe_load(path.read_text())
    changes: list[str] = []

    if (v := obj.get("co_type")) in CO_TYPE_MAP:
        obj["co_type"] = CO_TYPE_MAP[v]
        changes.append(f"co_type: {v} -> {obj['co_type']}")

    if (v := obj.get("stage")) in STAGE_MAP:
        obj["stage"] = STAGE_MAP[v]
        changes.append(f"stage: {v} -> {obj['stage']}")

    if (v := obj.get("risk_band")) in RISK_MAP:
        obj["risk_band"] = RISK_MAP[v]
        changes.append(f"risk_band: {v} -> {obj['risk_band']}")

    if (v := obj.get("cost_band")) in COST_MAP:
        obj["cost_band"] = COST_MAP[v]
        changes.append(f"cost_band: {v} -> {obj['cost_band']}")

    if (v := obj.get("lifecycle_state")) in LIFECYCLE_MAP:
        obj["lifecycle_state"] = LIFECYCLE_MAP[v]
        changes.append(f"lifecycle_state: {v} -> {obj['lifecycle_state']}")

    if obj.get("risk_band") in ("high", "expert_only"):
        sd = obj.setdefault("structured_data", {}) or {}
        if not sd.get("safety_boundary"):
            sd["safety_boundary"] = DEFAULT_SAFETY_BOUNDARY
            obj["structured_data"] = sd
            changes.append("added structured_data.safety_boundary")

    if changes:
        path.write_text(yaml.dump(obj, sort_keys=False, allow_unicode=True))
    return bool(changes), changes


def normalize_edges(edges_csv: Path, draft_slugs: set[str]) -> tuple[int, int]:
    """Remap edge_type synonyms and drop edges with unknown targets."""
    import csv

    with edges_csv.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    kept: list[dict] = []
    dropped = 0
    remapped = 0
    for row in rows:
        if row["target_id"] not in draft_slugs:
            dropped += 1
            continue
        if (et := row.get("edge_type")) in EDGE_TYPE_MAP:
            row["edge_type"] = EDGE_TYPE_MAP[et]
            remapped += 1
        kept.append(row)

    with edges_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    return remapped, dropped


def main(project_dir: str) -> int:
    project = Path(project_dir)
    drafts = project / "drafts"
    files = sorted(drafts.glob("*.yaml"))
    changed = 0
    draft_slugs: set[str] = set()
    for f in files:
        if f.name.startswith("_") or f.name in ("canonicalization_log.json",):
            continue
        did_change, changes = normalize_file(f)
        if did_change:
            changed += 1
            print(f"{f.name}:")
            for c in changes:
                print(f"  {c}")
        obj = yaml.safe_load(f.read_text())
        slug = obj.get("slug") or obj.get("id", f.stem)
        draft_slugs.add(slug)
    print(f"\nNormalized {changed} draft files; {len(draft_slugs)} slugs")

    edges_csv = project / "edges" / "edges.csv"
    if edges_csv.exists():
        remapped, dropped = normalize_edges(edges_csv, draft_slugs)
        print(f"Edges: {remapped} remapped, {dropped} dropped (unknown target)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ingestion/projects/ggg-2026-03"))
