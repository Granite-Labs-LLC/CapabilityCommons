from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.config import get_settings
from capability_commons.db.models import (
    ContextObject,
    ContextObjectVersion,
    ContradictionCase,
    ReviewRecord,
    RetrievalRun,
    RetrievalStep,
)
from capability_commons.domain.enums import LifecycleState, RetrievalRunStatus, RetrievalStepType, ReviewOutcome
from capability_commons.graph.adapters.relational_graph import RelationalGraphAdapter
from capability_commons.retrieval.intent import infer_intent
from capability_commons.retrieval.planner import RetrievalPlanner
from capability_commons.schemas.common import CitationSnippet
from capability_commons.schemas.retrieval import (
    EvidenceNode,
    EvidencePackResponse,
    RetrievalPlan,
    RetrievalRequest,
    RetrievalRunResponse,
    RetrievalStepResponse,
)
from capability_commons.search.adapters.postgres_search import PostgresSearchAdapter
from capability_commons.services.embedding import EmbeddingService
from capability_commons.services.evidence import EvidenceService
from capability_commons.services.helpers import get_version


class RetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.planner = RetrievalPlanner()
        self.search = PostgresSearchAdapter(session)
        self.graph = RelationalGraphAdapter(session)
        self.evidence = EvidenceService(session)
        self.embeddings = EmbeddingService(session)

    def compile_plan(self, task_spec: RetrievalRequest) -> RetrievalPlan:
        return self.planner.compile_plan(self._with_resolved_intent(task_spec))

    @staticmethod
    def _with_resolved_intent(task_spec: RetrievalRequest) -> RetrievalRequest:
        """Return a copy of `task_spec` with `intent` filled via heuristic
        inference if the caller left it unset (per PLAN.md retrieval P0-5)."""
        if task_spec.intent is not None:
            return task_spec
        return task_spec.model_copy(update={"intent": infer_intent(task_spec.query)})

    async def execute_plan(self, task_spec: RetrievalRequest) -> EvidencePackResponse:
        task_spec = self._with_resolved_intent(task_spec)
        plan = self.compile_plan(task_spec)
        run = RetrievalRun(
            workspace_id=task_spec.workspace_id,
            requester_id=task_spec.requester_id,
            intent=task_spec.intent,
            query_text=task_spec.query,
            task_spec=task_spec.model_dump(mode="json"),
            compiled_plan=plan.model_dump(mode="json"),
            budget_snapshot=task_spec.budgets.model_dump(mode="json"),
        )
        self.session.add(run)
        await self.session.flush()

        iteration = 1
        seed_nodes = [
            {"node_kind": "object_version", "id": version_id}
            for version_id in await self._resolve_seed_versions(task_spec)
        ]
        await self._log_step(
            run.id,
            iteration,
            RetrievalStepType.RESOLVE_SEEDS,
            query_text=task_spec.query,
            inputs={"seed_object_ids": [str(s) for s in task_spec.seed_object_ids], "seed_entity_ids": [str(s) for s in task_spec.seed_entity_ids]},
            outputs={"seed_nodes": [{"node_kind": seed["node_kind"], "id": str(seed["id"])} for seed in seed_nodes]},
            started_at=time.perf_counter(),
        )

        started_at = time.perf_counter()
        query_embedding = await self.embeddings.embed_query(task_spec.query)
        hits = await self.search.search_hybrid(
            workspace_id=task_spec.workspace_id,
            query=task_spec.query,
            query_embedding=query_embedding,
            filters=task_spec.facet_filters,
            top_k=plan.search_top_k,
            only_published=True,
            attributes=task_spec.attribute_filters,
        )
        await self._log_step(
            run.id,
            iteration,
            RetrievalStepType.SEARCH,
            query_text=task_spec.query,
            inputs={"filters": task_spec.facet_filters, "top_k": plan.search_top_k, "hybrid": query_embedding is not None},
            outputs={"hit_count": len(hits), "version_ids": [str(hit.version_id) for hit in hits]},
            started_at=started_at,
        )

        graph_edges = []
        graph_hits = []
        if plan.graph_depth > 0:
            graph_seed_nodes = [*seed_nodes, *[{"node_kind": "object_version", "id": hit.version_id} for hit in hits[:5]]]
            started_at = time.perf_counter()
            graph_edges = await self.graph.neighbors(
                graph_seed_nodes,
                edge_types=plan.edge_types,
                depth=plan.graph_depth,
                filters={"workspace_id": task_spec.workspace_id},
            )
            # Resolve graph-expanded version IDs not already in search hits
            search_version_ids = {h.version_id for h in hits}
            graph_version_ids = set()
            for edge in graph_edges:
                if edge.dst_node_kind == "object_version" and edge.dst_id not in search_version_ids:
                    graph_version_ids.add(edge.dst_id)
            if graph_version_ids:
                graph_hits = await self._resolve_graph_candidates(
                    list(graph_version_ids), task_spec.workspace_id
                )
            await self._log_step(
                run.id,
                iteration,
                RetrievalStepType.GRAPH_EXPAND,
                inputs={"seed_count": len(graph_seed_nodes), "edge_types": plan.edge_types, "depth": plan.graph_depth},
                outputs={
                    "edge_count": len(graph_edges),
                    "graph_candidate_count": len(graph_hits),
                    "edge_ids": [str(edge.id) for edge in graph_edges],
                },
                started_at=started_at,
            )

        # Merge search hits + graph candidates for reranking
        all_candidates = list(hits) + graph_hits
        started_at = time.perf_counter()
        reranked = await self._rerank_hits(all_candidates, task_spec, graph_version_ids=graph_version_ids if graph_edges else set())
        await self._log_step(
            run.id,
            iteration,
            RetrievalStepType.RERANK,
            inputs={"hit_count": len(hits), "graph_candidate_count": len(graph_hits)},
            outputs={"top_version_ids": [str(hit["version_id"]) for hit in reranked[:10]]},
            started_at=started_at,
        )

        started_at = time.perf_counter()
        sufficiency_score = self._compute_sufficiency(reranked, task_spec)
        await self._log_step(
            run.id,
            iteration,
            RetrievalStepType.SUFFICIENCY,
            inputs={"required_evidence": task_spec.required_evidence.model_dump(mode="json")},
            outputs={"sufficiency_score": sufficiency_score},
            started_at=started_at,
        )

        started_at = time.perf_counter()
        pack = await self._assemble_pack(run.id, task_spec, plan, reranked, sufficiency_score)
        await self._log_step(
            run.id,
            iteration,
            RetrievalStepType.ASSEMBLE,
            inputs={"candidate_count": len(reranked)},
            outputs={"evidence_count": len(pack.evidence)},
            started_at=started_at,
        )

        run.status = (
            RetrievalRunStatus.COMPLETED
            if float(sufficiency_score) >= self.settings.default_sufficiency_threshold
            else RetrievalRunStatus.BUDGET_EXHAUSTED
        )
        run.sufficiency_score = Decimal(str(round(float(sufficiency_score), 3)))
        run.result_summary = pack.model_dump(mode="json")
        run.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        return pack

    async def render_evidence_pack(self, run_id: uuid.UUID, format: str = "json") -> dict[str, Any] | str:
        run = await self.session.get(RetrievalRun, run_id)
        if run is None:
            raise ValueError(f"Retrieval run {run_id} not found")
        if format == "json":
            return run.result_summary
        if format == "markdown":
            summary = run.result_summary
            lines = [f"# Evidence Pack — {summary.get('intent', run.intent.value)}", "", f"**Query:** {summary.get('query', run.query_text)}", ""]
            for idx, evidence in enumerate(summary.get("evidence", []), start=1):
                lines.append(f"## {idx}. {evidence['title']}")
                lines.append(f"- Type: `{evidence['type']}`")
                lines.append(f"- Score: {evidence['score']}")
                if evidence.get("summary_short"):
                    lines.append(f"- Summary: {evidence['summary_short']}")
                if evidence.get("rationale"):
                    lines.append(f"- Why included: {evidence['rationale']}")
                for citation in evidence.get("citations", []):
                    lines.append(f"  - Citation: {citation['source_title']} — {citation['excerpt']}")
                lines.append("")
            return "\n".join(lines)
        raise ValueError(f"Unsupported format: {format}")

    async def get_run(self, run_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> RetrievalRunResponse:
        run = await self.session.get(RetrievalRun, run_id)
        if run is None:
            raise ValueError(f"Retrieval run {run_id} not found")
        if workspace_id is not None and run.workspace_id != workspace_id:
            raise ValueError(f"Retrieval run {run_id} not found")
        return RetrievalRunResponse.model_validate(run, from_attributes=True)

    async def get_steps(self, run_id: uuid.UUID, workspace_id: uuid.UUID | None = None) -> list[RetrievalStepResponse]:
        if workspace_id is not None:
            run = await self.session.get(RetrievalRun, run_id)
            if run is None or run.workspace_id != workspace_id:
                raise ValueError(f"Retrieval run {run_id} not found")
        result = await self.session.execute(
            select(RetrievalStep).where(RetrievalStep.retrieval_run_id == run_id).order_by(RetrievalStep.iteration_no.asc(), RetrievalStep.created_at.asc())
        )
        return [RetrievalStepResponse.model_validate(step, from_attributes=True) for step in result.scalars().all()]

    async def _resolve_seed_versions(self, task_spec: RetrievalRequest) -> list[uuid.UUID]:
        if not task_spec.seed_object_ids:
            return []
        result = await self.session.execute(
            select(ContextObject.current_version_id).where(ContextObject.id.in_(task_spec.seed_object_ids))
        )
        return [version_id for version_id in result.scalars().all() if version_id is not None]

    async def _resolve_graph_candidates(self, version_ids: list[uuid.UUID], workspace_id: uuid.UUID):
        """Load SearchHit-like objects for graph-expanded version IDs."""
        from capability_commons.schemas.search import SearchHit

        result = await self.session.execute(
            select(ContextObjectVersion, ContextObject)
            .join(ContextObject, ContextObjectVersion.context_object_id == ContextObject.id)
            .where(
                ContextObjectVersion.id.in_(version_ids),
                ContextObject.workspace_id == workspace_id,
            )
        )
        hits = []
        for version, obj in result.all():
            hits.append(SearchHit(
                object_id=obj.id,
                version_id=version.id,
                slug=obj.slug,
                type=obj.type,
                title=version.title,
                summary_short=version.summary_short,
                plain_language=version.plain_language,
                score=0.0,  # No search score; graph bonus applied in rerank
                lifecycle_state=obj.lifecycle_state,
                validity_status=version.validity_status.value,
                facets={},
            ))
        return hits

    async def _rerank_hits(
        self,
        hits,
        task_spec: RetrievalRequest,
        graph_version_ids: set[uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        if not hits:
            return []
        graph_version_ids = graph_version_ids or set()
        review_counts = await self._review_counts([hit.version_id for hit in hits])
        citations = await self._citations_for_versions([hit.version_id for hit in hits])

        reranked: list[dict[str, Any]] = []
        for hit in hits:
            search_score = float(hit.score)
            review_count = review_counts.get(hit.version_id, 0)
            citation_count = len(citations.get(hit.version_id, []))
            facet_bonus = 0.05 * len(hit.facets)
            published_bonus = 0.15 if hit.lifecycle_state == LifecycleState.PUBLISHED else 0.0
            verified_bonus = 0.15 if (task_spec.required_evidence.prefer_verified and review_count > 0) else 0.0
            citation_bonus = min(0.10, 0.02 * citation_count) if (task_spec.required_evidence.must_cite_sources and citation_count > 0) else 0.0
            graph_bonus = 0.10 if hit.version_id in graph_version_ids else 0.0

            score = search_score + published_bonus + verified_bonus + citation_bonus + facet_bonus + graph_bonus
            reranked.append(
                {
                    "object_id": hit.object_id,
                    "version_id": hit.version_id,
                    "slug": hit.slug,
                    "title": hit.title,
                    "type": hit.type.value,
                    "summary_short": hit.summary_short,
                    "score": round(score, 4),
                    "search_score": round(search_score, 4),
                    "graph_bonus": round(graph_bonus, 4),
                    "published_bonus": round(published_bonus, 4),
                    "verified_bonus": round(verified_bonus, 4),
                    "citation_bonus": round(citation_bonus, 4),
                    "facet_bonus": round(facet_bonus, 4),
                    "review_count": review_count,
                    "citations": citations.get(hit.version_id, []),
                }
            )
        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked

    def _compute_sufficiency(self, reranked: list[dict[str, Any]], task_spec: RetrievalRequest) -> float:
        if not reranked:
            return 0.0
        top = reranked[: max(1, task_spec.required_evidence.min_reviewed_objects)]
        reviewed_count = sum(1 for item in top if item["review_count"] > 0)
        cited_count = sum(1 for item in top if item["citations"])
        review_fraction = reviewed_count / max(1, task_spec.required_evidence.min_reviewed_objects)
        citation_fraction = 1.0 if not task_spec.required_evidence.must_cite_sources else cited_count / max(1, len(top))
        relevance_fraction = min(1.0, sum(float(item["score"]) for item in top) / max(1.0, 1.5 * len(top)))
        return round((0.4 * review_fraction) + (0.3 * citation_fraction) + (0.3 * relevance_fraction), 4)

    async def _assemble_pack(
        self,
        run_id: uuid.UUID,
        task_spec: RetrievalRequest,
        plan: RetrievalPlan,
        reranked: list[dict[str, Any]],
        sufficiency_score: float,
    ) -> EvidencePackResponse:
        top_items = reranked[:8]
        structured_by_version = await self._load_structured_data(
            [item["version_id"] for item in top_items]
        )
        evidence_nodes: list[EvidenceNode] = []
        for item in top_items:
            rationale = self._build_rationale(task_spec, item)
            citations = [CitationSnippet.model_validate(citation) for citation in item["citations"]]
            evidence_nodes.append(
                EvidenceNode(
                    object_id=item["object_id"],
                    version_id=item["version_id"],
                    slug=item["slug"],
                    title=item["title"],
                    type=item["type"],
                    score=item["score"],
                    summary_short=item["summary_short"],
                    citations=citations,
                    rationale=rationale,
                    structured_data=structured_by_version.get(item["version_id"]),
                )
            )
        contradictions = await self._contradiction_summary([node.version_id for node in evidence_nodes])
        next_steps = await self._next_steps([node.version_id for node in evidence_nodes[:3]])
        pack = EvidencePackResponse(
            run_id=run_id,
            intent=task_spec.intent,
            query=task_spec.query,
            plan=plan,
            sufficiency_score=sufficiency_score,
            evidence=evidence_nodes,
            contradictions=contradictions,
            next_steps=next_steps,
        )
        pack.rendered_markdown = await self.render_evidence_pack_from_pack(pack)
        return pack

    async def render_evidence_pack_from_pack(self, pack: EvidencePackResponse) -> str:
        lines = [f"# Evidence Pack — {pack.intent.value}", "", f"**Query:** {pack.query}", "", f"**Sufficiency:** {pack.sufficiency_score}", ""]
        for index, node in enumerate(pack.evidence, start=1):
            lines.append(f"## {index}. {node.title}")
            lines.append(f"- Type: `{node.type}`")
            lines.append(f"- Score: {node.score}")
            if node.summary_short:
                lines.append(f"- Summary: {node.summary_short}")
            if node.rationale:
                lines.append(f"- Rationale: {node.rationale}")
            for citation in node.citations:
                lines.append(f"  - {citation.source_title}: {citation.excerpt}")
            lines.append("")
        return "\n".join(lines)

    async def _load_structured_data(
        self, version_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[str, Any]]:
        if not version_ids:
            return {}
        result = await self.session.execute(
            select(ContextObjectVersion.id, ContextObjectVersion.structured_data)
            .where(ContextObjectVersion.id.in_(version_ids))
        )
        return {vid: data for vid, data in result.all() if data}

    async def _review_counts(self, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not version_ids:
            return {}
        result = await self.session.execute(
            select(ReviewRecord.context_object_version_id, func.count(ReviewRecord.id))
            .where(
                ReviewRecord.context_object_version_id.in_(version_ids),
                ReviewRecord.outcome.in_([ReviewOutcome.APPROVED, ReviewOutcome.VERIFIED]),
            )
            .group_by(ReviewRecord.context_object_version_id)
        )
        return {version_id: count for version_id, count in result.all()}

    async def _citations_for_versions(self, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict[str, Any]]]:
        grouped: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
        for version_id in version_ids:
            grouped[version_id] = await self.evidence.list_citations_for_version(version_id)
        return grouped

    async def _contradiction_summary(self, version_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
        if not version_ids:
            return []
        result = await self.session.execute(
            select(ContradictionCase)
            .where(
                (ContradictionCase.left_version_id.in_(version_ids))
                | (ContradictionCase.right_version_id.in_(version_ids))
            )
            .order_by(ContradictionCase.opened_at.desc())
            .limit(10)
        )
        return [
            {
                "contradiction_id": case.id,
                "dimension": case.dimension.value,
                "severity": case.severity.value,
                "status": case.status.value,
            }
            for case in result.scalars().all()
        ]

    async def _next_steps(self, version_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
        if not version_ids:
            return []
        prereq_map = await self.graph.reverse_prerequisites(version_ids)
        steps: list[dict[str, Any]] = []
        for dst_id, src_ids in prereq_map.items():
            for src_id in src_ids[:3]:
                version = await get_version(self.session, src_id)
                steps.append(
                    {
                        "version_id": version.id,
                        "title": version.title,
                        "type": version.context_object.type.value,
                        "for_version_id": dst_id,
                    }
                )
        return steps

    def _build_rationale(self, task_spec: RetrievalRequest, item: dict[str, Any]) -> str:
        reasons = [f"ranked highly for `{task_spec.intent.value}`"]
        if item["review_count"] > 0:
            reasons.append("has approved or verified review history")
        if item["citations"]:
            reasons.append("includes direct citations")
        if task_spec.facet_filters:
            reasons.append("matches requested context filters")
        return "; ".join(reasons)

    async def _log_step(
        self,
        run_id: uuid.UUID,
        iteration_no: int,
        step_type: RetrievalStepType,
        *,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        started_at: float,
        query_text: str | None = None,
    ) -> None:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        step = RetrievalStep(
            retrieval_run_id=run_id,
            iteration_no=iteration_no,
            step_type=step_type,
            query_text=query_text,
            inputs=inputs,
            outputs=outputs,
            latency_ms=latency_ms,
            budget_spent={"latency_ms": latency_ms},
        )
        self.session.add(step)
        await self.session.flush()
