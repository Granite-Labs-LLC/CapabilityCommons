"""Conversation memory service for multi-turn ask sessions.

Stores and retrieves conversation turns so follow-up queries can
incorporate context from prior turns. Each turn records the query,
resolved intent, and a summary of the answer for context injection.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ConversationTurn

MAX_CONTEXT_TURNS = 5  # Max prior turns to inject into retrieval context


class ConversationMemory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_conversation_id(
        self, conversation_id: uuid.UUID | None
    ) -> tuple[uuid.UUID, bool]:
        """Return (conversation_id, is_new). Generates a new ID if None provided."""
        if conversation_id is None:
            return uuid.uuid4(), True
        # Check if any turns exist for this conversation
        count = await self.session.scalar(
            select(func.count()).where(ConversationTurn.conversation_id == conversation_id)
        )
        return conversation_id, (count == 0)

    async def get_prior_turns(
        self,
        conversation_id: uuid.UUID,
        max_turns: int = MAX_CONTEXT_TURNS,
    ) -> list[ConversationTurn]:
        """Retrieve the most recent turns for a conversation, ordered by turn_number."""
        result = await self.session.execute(
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation_id)
            .order_by(ConversationTurn.turn_number.desc())
            .limit(max_turns)
        )
        turns = list(result.scalars().all())
        turns.reverse()  # Return in chronological order
        return turns

    async def save_turn(
        self,
        conversation_id: uuid.UUID,
        workspace_id: uuid.UUID,
        query: str,
        resolved_intent: str,
        retrieval_run_id: uuid.UUID | None = None,
        answer_summary: str | None = None,
        context_json: dict | None = None,
    ) -> ConversationTurn:
        """Save a new turn to the conversation."""
        # Get next turn number
        max_turn = await self.session.scalar(
            select(func.max(ConversationTurn.turn_number))
            .where(ConversationTurn.conversation_id == conversation_id)
        )
        turn_number = (max_turn or 0) + 1

        turn = ConversationTurn(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            turn_number=turn_number,
            query=query,
            resolved_intent=resolved_intent,
            retrieval_run_id=retrieval_run_id,
            answer_summary=answer_summary,
            context_json=context_json,
        )
        self.session.add(turn)
        await self.session.flush()
        return turn

    def build_context_prefix(self, prior_turns: list[ConversationTurn]) -> str:
        """Build a context prefix string from prior turns for query augmentation.

        This prefix is prepended to the current query to give the retrieval
        system awareness of conversational context.
        """
        if not prior_turns:
            return ""
        lines: list[str] = ["Prior conversation context:"]
        for turn in prior_turns:
            lines.append(f"- Q: {turn.query}")
            if turn.answer_summary:
                lines.append(f"  A: {turn.answer_summary}")
        lines.append("")
        return "\n".join(lines)
