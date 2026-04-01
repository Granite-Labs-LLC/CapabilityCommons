from __future__ import annotations

import hashlib

from fastapi import APIRouter, Request
from sqlalchemy import insert

from capability_commons.api.deps import DBSession
from capability_commons.db.models import Feedback
from capability_commons.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    session: DBSession,
) -> FeedbackResponse:
    """Submit anonymous user feedback on an answer or object."""
    # Hash the IP for basic spam detection without storing PII
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    stmt = (
        insert(Feedback)
        .values(
            action=body.action,
            answer_id=body.answer_id,
            run_id=body.run_id,
            object_slug=body.object_slug,
            comment=body.comment,
            ip_hash=ip_hash,
        )
        .returning(Feedback.id, Feedback.action, Feedback.created_at)
    )
    result = await session.execute(stmt)
    await session.commit()
    row = result.one()
    return FeedbackResponse(id=row.id, action=row.action, created_at=row.created_at)
