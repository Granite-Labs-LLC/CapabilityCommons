from __future__ import annotations

import logging

from fastapi import APIRouter

from capability_commons.api.deps import DBSession, PublicWorkspace
from capability_commons.domain.enums import RetrievalIntent
from capability_commons.retrieval.answer_composer import compose_answer
from capability_commons.retrieval.conversation_memory import ConversationMemory
from capability_commons.retrieval.intent_classifier import classify_intent
from capability_commons.retrieval.service import RetrievalService
from capability_commons.schemas.ask import AskRequest, AskResponse
from capability_commons.schemas.retrieval import RetrievalRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _detect_intent(query: str) -> RetrievalIntent:
    """Classify query intent using the weighted pattern classifier."""
    return classify_intent(query)


def _build_facet_filters(request: AskRequest) -> dict[str, list[str]]:
    """Convert AskContext into facet_filters for retrieval."""
    filters: dict[str, list[str]] = {}
    if request.context:
        ctx = request.context
        if ctx.housing_type:
            filters["housing_type"] = [ctx.housing_type]
        if ctx.climate_zone:
            filters["climate_zone"] = [ctx.climate_zone]
        if ctx.budget_profile:
            filters["budget_profile"] = [ctx.budget_profile]
        if ctx.settlement_type:
            filters["settlement_type"] = [ctx.settlement_type]
    return filters


@router.post("/public/ask", response_model=AskResponse)
async def public_ask(
    request: AskRequest,
    session: DBSession,
    workspace: PublicWorkspace,
) -> AskResponse:
    memory = ConversationMemory(session)

    # Resolve or create conversation_id
    conversation_id, is_new = await memory.get_or_create_conversation_id(request.conversation_id)

    # Resolve intent
    resolved_intent = request.intent or _detect_intent(request.query)

    # Augment query with conversation context for follow-up turns
    query = request.query
    if not is_new:
        prior_turns = await memory.get_prior_turns(conversation_id)
        context_prefix = memory.build_context_prefix(prior_turns)
        if context_prefix:
            query = f"{context_prefix}Current question: {request.query}"

    # Build retrieval request
    retrieval_request = RetrievalRequest(
        workspace_id=workspace.id,
        query=query,
        intent=resolved_intent,
        facet_filters=_build_facet_filters(request),
    )
    retrieval_request.budgets.max_search_results = request.max_results * 4
    retrieval_request.budgets.max_segments = request.max_results * 3

    # Execute retrieval
    service = RetrievalService(session)
    evidence_pack = await service.execute_plan(retrieval_request)

    # Compose structured answer
    response = compose_answer(evidence_pack, resolved_intent, request)
    response.conversation_id = conversation_id

    # Save this turn to conversation memory
    answer_summary = response.action_now or response.answer[:200]
    await memory.save_turn(
        conversation_id=conversation_id,
        workspace_id=workspace.id,
        query=request.query,
        resolved_intent=resolved_intent.value,
        retrieval_run_id=evidence_pack.run_id,
        answer_summary=answer_summary,
        context_json=request.context.model_dump() if request.context else None,
    )

    return response
