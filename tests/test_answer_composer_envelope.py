"""compose_answer must surface the implementation envelope (PLAN P1-8)."""
from __future__ import annotations

import uuid

from capability_commons.domain.enums import RetrievalIntent
from capability_commons.retrieval.answer_composer import compose_answer
from capability_commons.schemas.ask import AskRequest
from capability_commons.schemas.retrieval import (
    EvidenceNode,
    EvidencePackResponse,
    RetrievalPlan,
)


_ENVELOPE = {
    "smallest_viable_version": "Pour 1 gallon into a clean food-grade jug.",
    "tools": ["measuring cup"],
    "materials": ["food-grade jug", "lid"],
    "expected_time": "10 minutes",
    "expected_cost": "free",
    "success_checks": [
        "Jug is sealed.",
        "Container is labeled with date.",
    ],
    "stop_conditions": [
        "Container smells off.",
        "Water is cloudy after settling.",
    ],
    "common_mistakes": ["Reusing milk jugs."],
    "when_to_escalate": ["No clean water source within 24h."],
    "variants": [],
}


def _pack_with_envelope(node_type: str = "skill_guide") -> EvidencePackResponse:
    node = EvidenceNode(
        object_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        slug="water.safe-storage",
        title="Safe Water Storage",
        type=node_type,
        score=0.85,
        summary_short="Store water safely.",
        structured_data={"implementation": _ENVELOPE},
    )
    plan = RetrievalPlan(
        intent=RetrievalIntent.HOW_TO,
        search_top_k=10,
        graph_depth=1,
        iteration_limit=1,
        edge_types=[],
        rerank_weights={},
    )
    return EvidencePackResponse(
        run_id=uuid.uuid4(),
        intent=RetrievalIntent.HOW_TO,
        query="how do I store water?",
        plan=plan,
        sufficiency_score=0.8,
        evidence=[node],
    )


def _request() -> AskRequest:
    return AskRequest(query="how do I store water?")


def test_action_now_uses_smallest_viable_version():
    pack = _pack_with_envelope()
    resp = compose_answer(pack, RetrievalIntent.HOW_TO, _request())
    assert resp.action_now == _ENVELOPE["smallest_viable_version"]


def test_first_step_carries_envelope_tools_and_time():
    pack = _pack_with_envelope()
    resp = compose_answer(pack, RetrievalIntent.HOW_TO, _request())
    assert len(resp.implementation_plan) >= 1
    first = resp.implementation_plan[0]
    assert first.step == 1
    assert first.action == _ENVELOPE["smallest_viable_version"]
    assert first.tools == _ENVELOPE["tools"]
    assert first.materials == _ENVELOPE["materials"]
    assert first.time_estimate == _ENVELOPE["expected_time"]
    assert first.source_slug == "water.safe-storage"


def test_steps_include_one_per_success_check():
    pack = _pack_with_envelope()
    resp = compose_answer(pack, RetrievalIntent.HOW_TO, _request())
    # 1 SVV step + 2 success_check steps
    assert len(resp.implementation_plan) == 3
    assert "Confirm: Jug is sealed." in resp.implementation_plan[1].action


def test_safety_block_uses_envelope_stops_and_escalation():
    pack = _pack_with_envelope()
    resp = compose_answer(pack, RetrievalIntent.HOW_TO, _request())
    assert resp.safety.stop_conditions == _ENVELOPE["stop_conditions"]
    assert resp.safety.when_to_get_help == _ENVELOPE["when_to_escalate"]
    # common_mistakes flow into warnings.
    assert "Reusing milk jugs." in resp.safety.warnings


def test_no_envelope_falls_back_to_title_steps():
    """concept_note has no envelope; composer should still produce a sensible
    step list from titles/summaries."""
    node = EvidenceNode(
        object_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        slug="concept.x",
        title="Concept",
        type="concept_note",
        score=0.5,
        summary_short="A concept",
    )
    plan = RetrievalPlan(
        intent=RetrievalIntent.WHY,
        search_top_k=10, graph_depth=1, iteration_limit=1,
        edge_types=[], rerank_weights={},
    )
    pack = EvidencePackResponse(
        run_id=uuid.uuid4(),
        intent=RetrievalIntent.WHY,
        query="why?",
        plan=plan,
        sufficiency_score=0.6,
        evidence=[node],
    )
    resp = compose_answer(pack, RetrievalIntent.WHY, _request())
    assert resp.action_now == "A concept"
    assert resp.implementation_plan[0].action == "A concept"
