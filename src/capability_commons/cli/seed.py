"""CLI seed command: load capability and curriculum nodes into Postgres."""
from __future__ import annotations

import asyncio
import csv
import uuid
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from capability_commons.db.models import (
    OutboxEvent,
    ContextObject,
    ContextObjectFacet,
    ContextObjectVersion,
    Edge,
    EvidenceSource,
    EvidenceSpan,
    Workspace,
)
from capability_commons.domain.enums import (
    COType,
    CostBand,
    EdgeType,
    EvidenceSourceKind,
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
    "module": COType.MODULE,
    "assessment": COType.ASSESSMENT,
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
    "COVERS": EdgeType.CONTAINS,
    "ASSESSED_BY": EdgeType.ASSESSED_BY,
    "EVALUATES": EdgeType.VALIDATED_BY,
    "PRECEDES": EdgeType.NEXT_STEP_FOR,
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


def normalize_edge_type(raw: str) -> EdgeType | None:
    """Normalize an edge type string to an EdgeType enum value.

    Accepts:
    - Legacy uppercase CSV names: 'REQUIRES', 'NEXT', 'COVERS', etc.
    - Canonical lowercase enum values: 'prerequisite_for', 'builds_on', etc.
    """
    if raw in SEED_EDGE_TO_EDGE_TYPE:
        return SEED_EDGE_TO_EDGE_TYPE[raw]
    try:
        return EdgeType(raw.lower())
    except ValueError:
        return None


def resolve_co_type(node: dict) -> COType:
    """Resolve object type from co_type or type field."""
    if co_type_str := node.get("co_type"):
        return COType(co_type_str.lower())
    return SEED_TYPE_TO_CO_TYPE[node["type"]]


def resolve_requires(node: dict) -> list[tuple[str, str, dict]]:
    """Extract (source_slug, target_slug, metadata) triples from requires field.

    Handles both flat list format:
        requires: ["a.b", "c.d"]

    And grouped format:
        requires:
          - mode: all_of
            ids: ["a.b", "c.d"]
    """
    src_slug = node["id"]
    triples: list[tuple[str, str, dict]] = []
    for item in node.get("requires", []):
        if isinstance(item, str):
            triples.append((src_slug, item, {}))
        elif isinstance(item, dict):
            mode = item.get("mode", "all_of")
            for req_id in item.get("ids", []):
                triples.append((src_slug, req_id, {"group_mode": mode}))
    return triples


def load_yaml_nodes(data_dir: Path) -> list[dict]:
    nodes_dir = data_dir / "canonical" / "nodes"
    nodes = []
    for yaml_file in sorted(nodes_dir.glob("*.yaml")):
        with open(yaml_file) as f:
            nodes.append(yaml.safe_load(f))
    return nodes


def load_edges(data_dir: Path) -> list[dict]:
    """Load all edges from edges.csv."""
    edges_file = data_dir / "imports" / "edges.csv"
    if not edges_file.exists():
        return []
    edges = []
    with open(edges_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
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
    if structured := node.get("structured_data"):
        sd.update(structured)
    if tags := node.get("tags"):
        sd["tags"] = tags
    if outputs := node.get("outputs"):
        sd["outputs"] = outputs
    if bundle_overrides := node.get("bundle_overrides"):
        sd["_bundle"] = bundle_overrides
    return sd


async def seed_graph(data_dir: Path, db_url: str) -> None:
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    nodes = load_yaml_nodes(data_dir)
    csv_edges = load_edges(data_dir)

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

            co_type = resolve_co_type(node)
            lifecycle_str = node.get("lifecycle_state", "published").lower()
            lifecycle = LifecycleState(lifecycle_str) if lifecycle_str else LifecycleState.PUBLISHED
            obj = ContextObject(
                workspace_id=workspace.id,
                slug=slug,
                type=co_type,
                canonical_title=node.get("canonical_title") or node["title"],
                lifecycle_state=lifecycle,
                visibility=VisibilityType.PUBLIC,
            )
            session.add(obj)
            await session.flush()

            estimated_minutes = None
            if hours := node.get("estimated_hours"):
                estimated_minutes = int(float(hours) * 60)

            version = ContextObjectVersion(
                context_object_id=obj.id,
                version_no=node.get("version_no", 1),
                title=node.get("canonical_title") or node["title"],
                summary_short=node.get("summary_short") or node.get("summary"),
                summary_medium=node.get("summary_medium"),
                summary_long=node.get("summary_long"),
                plain_language=node.get("plain_language", ""),
                markdown_body=node.get("markdown_body") or node.get("summary", ""),
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

            # Set current_version_id and mark as published
            obj.current_version_id = version.id
            obj.published_at = obj.created_at

            # Emit publish event so the worker indexes/embeds this version
            session.add(OutboxEvent(
                aggregate_type="context_object",
                aggregate_id=obj.id,
                event_type="version.published",
                payload={"object_id": str(obj.id), "version_id": str(version.id)},
            ))

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

        # 3. Insert PREREQUISITE_FOR edges from YAML requires field
        # Direction: src=prerequisite, dst=dependant
        # "A requires B" means B is_prerequisite_for A => Edge(src=B, dst=A)
        req_edges = 0
        for node in nodes:
            dependant_slug = node["id"]
            if dependant_slug not in slug_to_version_id:
                continue
            for _, prereq_id, meta in resolve_requires(node):
                if prereq_id not in slug_to_version_id:
                    print(f"  WARN: missing prerequisite target {prereq_id}")
                    continue
                prereq_vid = slug_to_version_id[prereq_id]
                dependant_vid = slug_to_version_id[dependant_slug]
                if await _edge_exists(prereq_vid, EdgeType.PREREQUISITE_FOR, dependant_vid):
                    continue
                edge = Edge(
                    workspace_id=workspace.id,
                    src_node_kind=NodeKind.OBJECT_VERSION,
                    src_id=prereq_vid,
                    edge_type=EdgeType.PREREQUISITE_FOR,
                    dst_node_kind=NodeKind.OBJECT_VERSION,
                    dst_id=dependant_vid,
                    ordinal=req_edges,
                    confidence=Decimal("1.0"),
                    provenance_method=ProvenanceMethod.HUMAN_AUTHORED,
                    status=RelationStatus.CURRENT,
                    metadata_json=meta,
                )
                session.add(edge)
                req_edges += 1

        # 3b. Insert suggested_edges from ingestion YAML
        sug_edges = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            for edge_spec in node.get("suggested_edges", []):
                target_id = edge_spec.get("target_id")
                edge_type_str = edge_spec.get("edge_type", "builds_on")
                if target_id not in slug_to_version_id:
                    print(f"  WARN: missing suggested_edge target {target_id}")
                    continue
                src_vid = slug_to_version_id[src_slug]
                dst_vid = slug_to_version_id[target_id]
                et = normalize_edge_type(edge_type_str)
                if et is None:
                    print(f"  WARN: unknown edge type {edge_type_str}")
                    continue
                if await _edge_exists(src_vid, et, dst_vid):
                    continue
                edge = Edge(
                    workspace_id=workspace.id,
                    src_node_kind=NodeKind.OBJECT_VERSION,
                    src_id=src_vid,
                    edge_type=et,
                    dst_node_kind=NodeKind.OBJECT_VERSION,
                    dst_id=dst_vid,
                    ordinal=sug_edges,
                    confidence=Decimal(str(edge_spec.get("confidence", 0.8))),
                    provenance_method=ProvenanceMethod.LLM_EXTRACTED,
                    status=RelationStatus.CURRENT,
                    metadata_json={},
                )
                session.add(edge)
                sug_edges += 1
        if sug_edges:
            print(f"  Created {sug_edges} suggested edges")

        # 3c. Insert citations as EvidenceSource + EvidenceSpan
        cit_count = 0
        for node in nodes:
            src_slug = node["id"]
            if src_slug not in slug_to_version_id:
                continue
            version_id = slug_to_version_id[src_slug]
            for citation in node.get("citations", []):
                for span in citation.get("support", []):
                    source_ext_id = span.get("source_id", "")
                    # Find-or-create EvidenceSource by external_id
                    es_result = await session.execute(
                        select(EvidenceSource).where(
                            EvidenceSource.external_id == source_ext_id
                        )
                    )
                    ev_source = es_result.scalar_one_or_none()
                    if ev_source is None:
                        ev_source = EvidenceSource(
                            workspace_id=workspace.id,
                            external_id=source_ext_id,
                            source_kind=EvidenceSourceKind.BOOK,
                            title=source_ext_id,
                            uri=source_ext_id,
                            metadata_json={},
                        )
                        session.add(ev_source)
                        await session.flush()

                    ev_span = EvidenceSpan(
                        source_id=ev_source.id,
                        context_object_version_id=version_id,
                        start_char=span.get("start_char", 0),
                        end_char=span.get("end_char", 0),
                        excerpt=span.get("excerpt", ""),
                        metadata_json={
                            "segment_id": span.get("segment_id", ""),
                            "claim_id": citation.get("claim_id", ""),
                            "claim_text": citation.get("claim_text", ""),
                            "support_strength": span.get("support_strength", ""),
                            "page_start": span.get("page_start"),
                            "page_end": span.get("page_end"),
                        },
                    )
                    session.add(ev_span)
                    cit_count += 1
        if cit_count:
            print(f"  Created {cit_count} evidence spans")

        # 4. Insert edges from edges.csv
        csv_edge_count = 0
        csv_edge_skipped = 0
        for row in csv_edges:
            src_slug = row["source_id"]
            dst_slug = row["target_id"]
            seed_type = row["edge_type"]

            edge_type = normalize_edge_type(seed_type)
            if edge_type is None:
                print(f"  WARN: unknown edge type {seed_type}, skipping")
                continue

            if src_slug not in slug_to_version_id or dst_slug not in slug_to_version_id:
                print(f"  WARN: missing edge node {src_slug} -> {dst_slug} ({seed_type})")
                continue

            src_vid = slug_to_version_id[src_slug]
            dst_vid = slug_to_version_id[dst_slug]

            if await _edge_exists(src_vid, edge_type, dst_vid):
                csv_edge_skipped += 1
                continue

            ordinal = None
            if seq := row.get("sequence"):
                try:
                    ordinal = int(seq)
                except (ValueError, TypeError):
                    pass

            conf_str = row.get("confidence", "")
            try:
                confidence = Decimal(conf_str) if conf_str else Decimal("1.0")
            except Exception:
                confidence = Decimal("1.0")

            edge = Edge(
                workspace_id=workspace.id,
                src_node_kind=NodeKind.OBJECT_VERSION,
                src_id=src_vid,
                edge_type=edge_type,
                dst_node_kind=NodeKind.OBJECT_VERSION,
                dst_id=dst_vid,
                ordinal=ordinal,
                confidence=confidence,
                provenance_method=ProvenanceMethod.HUMAN_AUTHORED,
                status=RelationStatus.CURRENT,
                metadata_json={"note": row.get("note", ""), "seed_edge_type": seed_type},
            )
            session.add(edge)
            csv_edge_count += 1

        await session.commit()

    await engine.dispose()
    print(f"Seed complete: {created} objects created, {skipped} skipped, "
          f"{req_edges} prerequisite edges (from YAML), "
          f"{csv_edge_count} CSV edges created, {csv_edge_skipped} CSV edges skipped (duplicates)")


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
    parser.add_argument("--data-dir", type=Path, required=True, help="Path to seed data directory")
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
