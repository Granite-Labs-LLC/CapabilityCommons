# Phase C: Seed Knowledge Graph — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an idempotent CLI command that loads 25 seed nodes + 77 edges from `expanded_seed/` YAML and CSV files into the Postgres database.

**Architecture:** A `cli.py` module with a `seed` command that reads YAML node files and edges.csv, maps them to SQLAlchemy models, and inserts via async session. Idempotent via slug uniqueness checks.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x (async), PyYAML, asyncio, click (or argparse)

---

### Task 1: Add PyYAML dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add pyyaml to dependencies**

Add `"pyyaml>=6.0,<7.0"` to the `dependencies` list in `pyproject.toml`, after `"python-slugify>=8.0,<9.0"`.

**Step 2: Install**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: pyyaml installs successfully

**Step 3: Verify**

Run: `source .venv/bin/activate && python3 -c "import yaml; print(yaml.__version__)"`
Expected: version string like `6.0.3`

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyyaml dependency for seed data loading

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Write seed loader module

**Files:**
- Create: `src/capability_commons/cli/__init__.py`
- Create: `src/capability_commons/cli/seed.py`

**Step 1: Create the cli package**

Create `src/capability_commons/cli/__init__.py` (empty file).

**Step 2: Write seed.py**

This module contains:
- `load_yaml_nodes(data_dir: Path) -> list[dict]` — reads all `canonical/nodes/*.yaml` files
- `load_next_edges(data_dir: Path) -> list[dict]` — reads `imports/edges.csv`, filters to NEXT edges only
- `map_co_type(seed_type: str) -> COType` — maps `skill`→`skill_guide`, `concept`→`concept_note`, `project`→`project_blueprint`
- `map_facets(node: dict) -> list[tuple[FacetType, str]]` — maps contexts + domain to facet records
- `build_structured_data(node: dict) -> dict` — merges payload, tags, and outputs into structured_data JSONB
- `async def seed_graph(data_dir: Path, db_url: str) -> None` — main orchestrator

```python
"""CLI seed command: load the 25-node starter graph into Postgres."""
from __future__ import annotations

import asyncio
import csv
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.db.models import (
    ContextObject,
    ContextObjectFacet,
    ContextObjectVersion,
    Edge,
    Workspace,
)
from capability_commons.domain.enums import (
    COType,
    CostBand,
    EdgeType,
    FacetType,
    LifecycleState,
    NodeKind,
    ProvenanceMethod,
    RelationStatus,
    RiskBand,
    StageType,
    ValidityStatus,
    VisibilityType,
    WorkspaceVisibility,
)

SEED_TYPE_TO_CO_TYPE = {
    "skill": COType.SKILL_GUIDE,
    "concept": COType.CONCEPT_NOTE,
    "project": COType.PROJECT_BLUEPRINT,
}

CONTEXT_TO_FACET: dict[str, tuple[FacetType, str]] = {
    "general": (FacetType.AUDIENCE, "general"),
    "renter": (FacetType.AUDIENCE, "renter"),
    "homeowner": (FacetType.AUDIENCE, "homeowner"),
    "urban": (FacetType.SETTLEMENT_TYPE, "urban"),
    "rural": (FacetType.SETTLEMENT_TYPE, "rural"),
    "off_grid": (FacetType.SETTLEMENT_TYPE, "off_grid"),
    "low_budget": (FacetType.BUDGET_PROFILE, "low_budget"),
}

SEED_EDGE_TO_EDGE_TYPE = {
    "REQUIRES": EdgeType.PREREQUISITE_FOR,
    "NEXT": EdgeType.NEXT_STEP_FOR,
}

STAGE_MAP = {
    "foundation": StageType.FOUNDATION,
    "household": StageType.HOUSEHOLD,
    "productive": StageType.PRODUCTIVE,
    "community": StageType.COMMUNITY,
    "advanced": StageType.ADVANCED,
}

COST_MAP = {
    "free": CostBand.FREE,
    "low": CostBand.LOW,
    "medium": CostBand.MEDIUM,
    "high": CostBand.HIGH,
}

RISK_MAP = {
    "low": RiskBand.LOW,
    "moderate": RiskBand.MODERATE,
    "high": RiskBand.HIGH,
    "expert_only": RiskBand.EXPERT_ONLY,
}


def load_yaml_nodes(data_dir: Path) -> list[dict]:
    nodes_dir = data_dir / "canonical" / "nodes"
    nodes = []
    for yaml_file in sorted(nodes_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            nodes.append(yaml.safe_load(f))
    return nodes


def load_next_edges(data_dir: Path) -> list[dict]:
    edges_file = data_dir / "imports" / "edges.csv"
    edges = []
    with open(edges_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["edge_type"] == "NEXT":
                edges.append(row)
    return edges


def map_facets(node: dict) -> list[tuple[FacetType, str]]:
    facets: list[tuple[FacetType, str]] = []
    # Domain facet
    if domain := node.get("primary_domain"):
        facets.append((FacetType.DOMAIN, domain))
    # Context facets
    for ctx in node.get("contexts", []):
        if mapping := CONTEXT_TO_FACET.get(ctx):
            facets.append(mapping)
    return facets


def build_structured_data(node: dict) -> dict:
    sd: dict = {}
    if payload := node.get("payload"):
        sd.update(payload)
    if tags := node.get("tags"):
        sd["tags"] = tags
    if outputs := node.get("outputs"):
        sd["outputs"] = outputs
    return sd


async def seed_graph(data_dir: Path, db_url: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    nodes = load_yaml_nodes(data_dir)
    next_edges = load_next_edges(data_dir)

    async with session_factory() as session:
        # 1. Ensure workspace exists
        workspace = await _ensure_workspace(session)

        # 2. Insert nodes, collect slug -> version_id mapping
        slug_to_version_id: dict[str, uuid.UUID] = {}
        slug_to_object_id: dict[str, uuid.UUID] = {}
        created = 0
        skipped = 0

        for node in nodes:
            slug = node["id"]
            # Check if already exists
            existing = await session.execute(
                select(ContextObject).where(
                    ContextObject.workspace_id == workspace.id,
                    ContextObject.slug == slug,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                # Still need IDs for edge creation
                obj = (await session.execute(
                    select(ContextObject).where(
                        ContextObject.workspace_id == workspace.id,
                        ContextObject.slug == slug,
                    )
                )).scalar_one()
                slug_to_object_id[slug] = obj.id
                slug_to_version_id[slug] = obj.current_version_id
                continue

            co_type = SEED_TYPE_TO_CO_TYPE[node["type"]]
            obj = ContextObject(
                workspace_id=workspace.id,
                slug=slug,
                type=co_type,
                canonical_title=node["title"],
                lifecycle_state=LifecycleState.DRAFT,
                visibility=VisibilityType.PUBLIC,
            )
            session.add(obj)
            await session.flush()

            estimated_minutes = None
            if hours := node.get("estimated_hours"):
                estimated_minutes = int(float(hours) * 60)

            version = ContextObjectVersion(
                context_object_id=obj.id,
                version_no=1,
                title=node["title"],
                summary_short=node.get("summary"),
                plain_language=node.get("plain_language", ""),
                markdown_body=node.get("summary", ""),
                structured_data=build_structured_data(node),
                validity_status=ValidityStatus.CURRENT,
                stage=STAGE_MAP.get(node.get("stage", ""), None),
                difficulty=node.get("difficulty"),
                estimated_minutes=estimated_minutes,
                cost_band=COST_MAP.get(node.get("cost_band", "free"), CostBand.FREE),
                risk_band=RISK_MAP.get(node.get("risk_band", "low"), RiskBand.LOW),
            )
            session.add(version)
            await session.flush()

            # Set current_version_id
            obj.current_version_id = version.id

            # Add facets
            for facet_type, facet_value in map_facets(node):
                session.add(ContextObjectFacet(
                    context_object_version_id=version.id,
                    facet_type=facet_type,
                    facet_value=facet_value,
                ))

            slug_to_object_id[slug] = obj.id
            slug_to_version_id[slug] = version.id
            created += 1

        await session.flush()

        # 3. Insert REQUIRES edges from YAML requires field
        req_edges = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            for req_group in node.get("requires", []):
                if not isinstance(req_group, dict):
                    continue
                for i, req_id in enumerate(req_group.get("ids", [])):
                    if req_id not in slug_to_version_id:
                        print(f"  WARN: missing prerequisite target {req_id}")
                        continue
                    edge = Edge(
                        workspace_id=workspace.id,
                        src_node_kind=NodeKind.OBJECT_VERSION,
                        src_id=slug_to_version_id[src_slug],
                        edge_type=EdgeType.PREREQUISITE_FOR,
                        dst_node_kind=NodeKind.OBJECT_VERSION,
                        dst_id=slug_to_version_id[req_id],
                        ordinal=i,
                        confidence=Decimal("1.0"),
                        provenance_method=ProvenanceMethod.HUMAN_AUTHORED,
                        status=RelationStatus.CURRENT,
                        metadata_json={"group_mode": req_group.get("mode", "all_of")},
                    )
                    session.add(edge)
                    req_edges += 1

        # 4. Insert NEXT edges from edges.csv
        nav_edges = 0
        for row in next_edges:
            src_slug = row["source_id"]
            dst_slug = row["target_id"]
            if src_slug not in slug_to_version_id or dst_slug not in slug_to_version_id:
                print(f"  WARN: missing NEXT edge node {src_slug} -> {dst_slug}")
                continue
            edge = Edge(
                workspace_id=workspace.id,
                src_node_kind=NodeKind.OBJECT_VERSION,
                src_id=slug_to_version_id[src_slug],
                edge_type=EdgeType.NEXT_STEP_FOR,
                dst_node_kind=NodeKind.OBJECT_VERSION,
                dst_id=slug_to_version_id[dst_slug],
                confidence=Decimal("1.0"),
                provenance_method=ProvenanceMethod.HUMAN_AUTHORED,
                status=RelationStatus.CURRENT,
                metadata_json={"note": row.get("note", "")},
            )
            session.add(edge)
            nav_edges += 1

        await session.commit()

    await engine.dispose()
    print(f"Seed complete: {created} objects created, {skipped} skipped, "
          f"{req_edges} prerequisite edges, {nav_edges} navigation edges")


async def _ensure_workspace(session: AsyncSession) -> Workspace:
    result = await session.execute(
        select(Workspace).where(Workspace.slug == "capability-commons")
    )
    ws = result.scalar_one_or_none()
    if ws:
        return ws
    ws = Workspace(
        slug="capability-commons",
        name="Capability Commons",
        visibility=WorkspaceVisibility.PUBLIC,
    )
    session.add(ws)
    await session.flush()
    return ws


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed the Capability Commons knowledge graph")
    parser.add_argument("--data-dir", type=Path, required=True, help="Path to expanded_seed directory")
    parser.add_argument("--db-url", type=str, default=None, help="Database URL (default: from .env)")
    args = parser.parse_args()

    if args.db_url is None:
        from capability_commons.config import get_settings
        db_url = get_settings().database_url
    else:
        db_url = args.db_url

    asyncio.run(seed_graph(args.data_dir, db_url))


if __name__ == "__main__":
    main()
```

**Step 3: Create `__main__.py` for `python -m` invocation**

Create `src/capability_commons/cli/__main__.py`:

```python
from capability_commons.cli.seed import main

main()
```

**Step 4: Commit**

```bash
git add src/capability_commons/cli/
git commit -m "feat: add seed CLI command for loading starter knowledge graph

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Write tests for seed helpers

**Files:**
- Create: `tests/test_seed.py`

**Step 1: Write unit tests for helper functions**

```python
from pathlib import Path

from capability_commons.cli.seed import (
    SEED_TYPE_TO_CO_TYPE,
    build_structured_data,
    load_next_edges,
    load_yaml_nodes,
    map_facets,
)
from capability_commons.domain.enums import COType, FacetType

SEED_DIR = Path(__file__).resolve().parents[1] / "expanded_seed"


def test_load_yaml_nodes_count():
    nodes = load_yaml_nodes(SEED_DIR)
    assert len(nodes) == 25


def test_load_yaml_nodes_has_required_fields():
    nodes = load_yaml_nodes(SEED_DIR)
    for node in nodes:
        assert "id" in node
        assert "type" in node
        assert "title" in node
        assert "plain_language" in node
        assert node["type"] in SEED_TYPE_TO_CO_TYPE


def test_load_next_edges():
    edges = load_next_edges(SEED_DIR)
    assert len(edges) == 27  # 77 total - 50 REQUIRES = 27 NEXT
    for e in edges:
        assert e["edge_type"] == "NEXT"


def test_map_co_type():
    assert SEED_TYPE_TO_CO_TYPE["skill"] == COType.SKILL_GUIDE
    assert SEED_TYPE_TO_CO_TYPE["concept"] == COType.CONCEPT_NOTE
    assert SEED_TYPE_TO_CO_TYPE["project"] == COType.PROJECT_BLUEPRINT


def test_map_facets():
    node = {
        "primary_domain": "water",
        "contexts": ["general", "renter", "urban", "low_budget"],
    }
    facets = map_facets(node)
    facet_types = [f[0] for f in facets]
    assert (FacetType.DOMAIN, "water") in facets
    assert (FacetType.AUDIENCE, "general") in facets
    assert (FacetType.AUDIENCE, "renter") in facets
    assert (FacetType.SETTLEMENT_TYPE, "urban") in facets
    assert (FacetType.BUDGET_PROFILE, "low_budget") in facets


def test_build_structured_data():
    node = {
        "payload": {"performance_statement": "Do the thing", "tools": ["hammer"]},
        "tags": ["repair", "tools"],
        "outputs": ["checklist"],
    }
    sd = build_structured_data(node)
    assert sd["performance_statement"] == "Do the thing"
    assert sd["tools"] == ["hammer"]
    assert sd["tags"] == ["repair", "tools"]
    assert sd["outputs"] == ["checklist"]


def test_build_structured_data_no_payload():
    node = {"tags": ["a"]}
    sd = build_structured_data(node)
    assert sd["tags"] == ["a"]
    assert "performance_statement" not in sd
```

**Step 2: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_seed.py -v`
Expected: all 7 tests pass

**Step 3: Commit**

```bash
git add tests/test_seed.py
git commit -m "test: add unit tests for seed helper functions

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Run the seed command

**Step 1: Run seed**

Run: `source .venv/bin/activate && python -m capability_commons.cli seed --data-dir expanded_seed/`
Expected: `Seed complete: 25 objects created, 0 skipped, 50 prerequisite edges, 27 navigation edges`

**Step 2: Verify objects in DB**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "SELECT slug, type, lifecycle_state FROM context_objects ORDER BY slug;"`
Expected: 25 rows with correct types and draft state

**Step 3: Verify versions**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "SELECT count(*) FROM context_object_versions;"`
Expected: `25`

**Step 4: Verify facets**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "SELECT facet_type, count(*) FROM context_object_facets GROUP BY facet_type ORDER BY facet_type;"`
Expected: rows for audience, budget_profile, domain, settlement_type

**Step 5: Verify edges**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "SELECT edge_type, count(*) FROM edges GROUP BY edge_type;"`
Expected: `prerequisite_for: 50, next_step_for: 27`

**Step 6: Verify idempotency — run again**

Run: `source .venv/bin/activate && python -m capability_commons.cli seed --data-dir expanded_seed/`
Expected: `Seed complete: 0 objects created, 25 skipped, ...`

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: seed knowledge graph — 25 nodes, 77 edges loaded

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Completion Checklist

- [ ] PyYAML dependency added
- [ ] `src/capability_commons/cli/seed.py` implemented
- [ ] `python -m capability_commons.cli seed` works
- [ ] 7 unit tests passing for helper functions
- [ ] 25 context_objects created with correct types
- [ ] 25 context_object_versions with structured_data
- [ ] Facets created (domain, audience, settlement_type, budget_profile)
- [ ] 50 prerequisite_for edges created
- [ ] 27 next_step_for edges created
- [ ] Idempotent re-run skips existing objects
