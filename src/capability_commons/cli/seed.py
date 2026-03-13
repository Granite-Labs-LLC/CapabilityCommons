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

        # Helper to check edge existence
        async def _edge_exists(src_id: uuid.UUID, edge_type: EdgeType, dst_id: uuid.UUID) -> bool:
            result = await session.execute(
                select(Edge).where(
                    Edge.workspace_id == workspace.id,
                    Edge.src_id == src_id,
                    Edge.edge_type == edge_type,
                    Edge.dst_id == dst_id,
                )
            )
            return result.scalar_one_or_none() is not None

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
                    src_vid = slug_to_version_id[src_slug]
                    dst_vid = slug_to_version_id[req_id]
                    if await _edge_exists(src_vid, EdgeType.PREREQUISITE_FOR, dst_vid):
                        continue
                    edge = Edge(
                        workspace_id=workspace.id,
                        src_node_kind=NodeKind.OBJECT_VERSION,
                        src_id=src_vid,
                        edge_type=EdgeType.PREREQUISITE_FOR,
                        dst_node_kind=NodeKind.OBJECT_VERSION,
                        dst_id=dst_vid,
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
            src_vid = slug_to_version_id[src_slug]
            dst_vid = slug_to_version_id[dst_slug]
            if await _edge_exists(src_vid, EdgeType.NEXT_STEP_FOR, dst_vid):
                continue
            edge = Edge(
                workspace_id=workspace.id,
                src_node_kind=NodeKind.OBJECT_VERSION,
                src_id=src_vid,
                edge_type=EdgeType.NEXT_STEP_FOR,
                dst_node_kind=NodeKind.OBJECT_VERSION,
                dst_id=dst_vid,
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
