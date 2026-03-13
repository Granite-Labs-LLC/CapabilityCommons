from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContextObject, ContextObjectVersion, Edge
from capability_commons.domain.enums import EdgeType, NodeKind
from capability_commons.graph.adapters.base import GraphAdapter


class RelationalGraphAdapter(GraphAdapter):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def neighbors(self, seed_nodes, edge_types, depth, filters=None):
        filters = filters or {}
        allowed_edge_types = set(edge_types or [])
        current_frontier = {(node["node_kind"], node["id"]) for node in seed_nodes}
        seen = set(current_frontier)
        collected: list[Edge] = []

        for _ in range(depth):
            if not current_frontier:
                break
            next_frontier = set()
            for node_kind, node_id in current_frontier:
                stmt = select(Edge).where(Edge.src_node_kind == node_kind, Edge.src_id == node_id)
                if allowed_edge_types:
                    stmt = stmt.where(Edge.edge_type.in_(list(allowed_edge_types)))
                if filters.get("workspace_id") is not None:
                    stmt = stmt.where(Edge.workspace_id == filters["workspace_id"])
                result = await self.session.execute(stmt.order_by(Edge.created_at.asc()))
                edges = list(result.scalars().all())
                collected.extend(edges)
                for edge in edges:
                    node_key = (edge.dst_node_kind, edge.dst_id)
                    if node_key not in seen:
                        next_frontier.add(node_key)
                        seen.add(node_key)
            current_frontier = next_frontier
        return collected

    async def paths_between(self, src, dst, edge_types, max_depth):
        frontier = [{"node_kind": src["node_kind"], "id": src["id"], "path": []}]
        visited = {(src["node_kind"], src["id"])}
        edge_types = set(edge_types or [])
        while frontier:
            current = frontier.pop(0)
            if len(current["path"]) >= max_depth:
                continue
            stmt = select(Edge).where(Edge.src_node_kind == current["node_kind"], Edge.src_id == current["id"])
            if edge_types:
                stmt = stmt.where(Edge.edge_type.in_(list(edge_types)))
            result = await self.session.execute(stmt)
            for edge in result.scalars().all():
                new_path = [*current["path"], edge]
                if edge.dst_node_kind == dst["node_kind"] and edge.dst_id == dst["id"]:
                    return new_path
                key = (edge.dst_node_kind, edge.dst_id)
                if key not in visited:
                    visited.add(key)
                    frontier.append({"node_kind": edge.dst_node_kind, "id": edge.dst_id, "path": new_path})
        return []

    async def ordered_members(self, group_version_id):
        stmt = (
            select(Edge, ContextObjectVersion, ContextObject)
            .join(ContextObjectVersion, ContextObjectVersion.id == Edge.dst_id)
            .join(ContextObject, ContextObject.id == ContextObjectVersion.context_object_id)
            .where(
                Edge.src_node_kind == NodeKind.OBJECT_VERSION,
                Edge.src_id == group_version_id,
                Edge.edge_type == EdgeType.CONTAINS,
                Edge.dst_node_kind == NodeKind.OBJECT_VERSION,
            )
            .order_by(Edge.ordinal.asc().nullslast(), ContextObjectVersion.created_at.asc())
        )
        result = await self.session.execute(stmt)
        members = []
        for edge, version, obj in result.all():
            members.append(
                {
                    "edge_id": edge.id,
                    "ordinal": edge.ordinal,
                    "object_id": obj.id,
                    "version_id": version.id,
                    "slug": obj.slug,
                    "type": obj.type.value,
                    "title": version.title,
                }
            )
        return members

    async def reverse_prerequisites(self, version_ids):
        if not version_ids:
            return {}
        stmt = select(Edge).where(
            Edge.edge_type == EdgeType.PREREQUISITE_FOR,
            Edge.dst_node_kind == NodeKind.OBJECT_VERSION,
            Edge.dst_id.in_(version_ids),
        )
        result = await self.session.execute(stmt)
        grouped: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for edge in result.scalars().all():
            grouped[edge.dst_id].append(edge.src_id)
        return grouped
