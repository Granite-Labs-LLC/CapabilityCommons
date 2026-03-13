import uuid

from capability_commons.domain.enums import RetrievalIntent
from capability_commons.retrieval.planner import RetrievalPlanner
from capability_commons.schemas.retrieval import RetrievalRequest


def test_compile_plan_for_learn_path() -> None:
    planner = RetrievalPlanner()
    request = RetrievalRequest(
        workspace_id=uuid.uuid4(),
        query='What should I learn next for outage prep?',
        intent=RetrievalIntent.LEARN_PATH,
    )
    plan = planner.compile_plan(request)
    assert 'prerequisite_for' in plan.edge_types
    assert plan.iteration_limit == request.budgets.max_iterations
