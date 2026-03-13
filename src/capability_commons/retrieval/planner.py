from __future__ import annotations

from capability_commons.domain.enums import EdgeType, RetrievalIntent
from capability_commons.schemas.retrieval import RetrievalPlan, RetrievalRequest


INTENT_EDGE_TYPES: dict[RetrievalIntent, list[EdgeType]] = {
    RetrievalIntent.HOW_TO: [
        EdgeType.SUPPORTED_BY,
        EdgeType.REQUIRES_TOOL,
        EdgeType.REQUIRES_MATERIAL,
        EdgeType.HAS_FAILURE_MODE,
        EdgeType.MITIGATED_BY,
        EdgeType.BOUNDED_BY,
    ],
    RetrievalIntent.LEARN_PATH: [
        EdgeType.PREREQUISITE_FOR,
        EdgeType.NEXT_STEP_FOR,
        EdgeType.BUILDS_ON,
        EdgeType.CONTAINS,
    ],
    RetrievalIntent.WHY: [
        EdgeType.SUPPORTED_BY,
        EdgeType.DERIVED_FROM,
        EdgeType.VALIDATED_BY,
        EdgeType.CONTRADICTED_BY,
    ],
    RetrievalIntent.COMPARE_OPTIONS: [
        EdgeType.ALTERNATIVE_TO,
        EdgeType.APPLIES_IN,
        EdgeType.ADAPTED_FOR,
        EdgeType.BOUNDED_BY,
    ],
    RetrievalIntent.LOCALIZE: [
        EdgeType.ADAPTED_FOR,
        EdgeType.APPLIES_IN,
        EdgeType.BOUNDED_BY,
        EdgeType.ALTERNATIVE_TO,
    ],
    RetrievalIntent.DEBUG_FAILURE: [
        EdgeType.HAS_FAILURE_MODE,
        EdgeType.MITIGATED_BY,
        EdgeType.CONTRADICTED_BY,
        EdgeType.SUPPORTED_BY,
    ],
    RetrievalIntent.TEACH_FORWARD: [
        EdgeType.CONTAINS,
        EdgeType.NEXT_STEP_FOR,
        EdgeType.ASSESSED_BY,
    ],
    RetrievalIntent.WHAT_CHANGED: [
        EdgeType.SUPERSEDES,
        EdgeType.CORRECTED_BY,
        EdgeType.DEPRECATED_BY,
        EdgeType.CONTRADICTED_BY,
    ],
    RetrievalIntent.SAFETY_CHECK: [
        EdgeType.UNSAFE_WITHOUT,
        EdgeType.BOUNDED_BY,
        EdgeType.MITIGATED_BY,
        EdgeType.CONTRADICTED_BY,
        EdgeType.VALIDATED_BY,
    ],
}


class RetrievalPlanner:
    def compile_plan(self, task: RetrievalRequest) -> RetrievalPlan:
        edge_types = [edge.value for edge in INTENT_EDGE_TYPES.get(task.intent, [])]
        weights = {
            "search_score": 0.45,
            "published_bonus": 0.15,
            "verified_bonus": 0.15 if task.required_evidence.prefer_verified else 0.0,
            "facet_match_bonus": 0.15,
            "citation_bonus": 0.10 if task.required_evidence.must_cite_sources else 0.0,
        }
        return RetrievalPlan(
            intent=task.intent,
            search_top_k=min(task.budgets.max_search_results, 50),
            graph_depth=task.budgets.max_graph_depth,
            iteration_limit=task.budgets.max_iterations,
            edge_types=edge_types,
            rerank_weights=weights,
        )
