"""Public contribution endpoints (FE-CTR-1).

These endpoints accept anonymous field reports and context adaptations
from the public site. They write structured rows into the existing
`feedback` table so the existing audit / review infrastructure can pick
them up (no new table required for the MVP).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from capability_commons.api.deps import DBSession, PublicWorkspace
from capability_commons.db.models import ContextObject, Feedback
from capability_commons.domain.enums import FeedbackAction

router = APIRouter()


FieldReportOutcome = Literal[
    "completed_as_described",
    "completed_with_modifications",
    "partially_completed",
    "could_not_complete",
    "found_safety_issue",
]


class FieldReportRequest(BaseModel):
    capability_slug: str = Field(..., min_length=1, max_length=255)
    outcome: FieldReportOutcome
    context: str | None = None
    what_worked: str | None = None
    what_didnt: str | None = None
    what_id_change: str | None = None
    contact: str | None = None


class AdaptationRequest(BaseModel):
    capability_slug: str = Field(..., min_length=1, max_length=255)
    variant_label: str = Field(..., min_length=1, max_length=80)
    when: str = Field(..., min_length=1, max_length=255)
    notes: str | None = None
    context: str | None = None
    contact: str | None = None


class ContributionResponse(BaseModel):
    feedback_id: str
    status: str = "accepted"


async def _slug_exists(session, workspace_id, slug: str) -> bool:
    row = await session.execute(
        select(ContextObject.id).where(
            ContextObject.workspace_id == workspace_id,
            ContextObject.slug == slug,
        )
    )
    return row.scalar_one_or_none() is not None


@router.post(
    "/contribute/field-report",
    response_model=ContributionResponse,
    status_code=201,
)
async def submit_field_report(
    request: FieldReportRequest,
    session: DBSession,
    workspace: PublicWorkspace,
) -> ContributionResponse:
    """Anonymous field-report submission. Stored as a `report_issue`
    feedback row whose payload carries the structured fields."""
    if not await _slug_exists(session, workspace.id, request.capability_slug):
        raise HTTPException(status_code=404, detail=f"Unknown capability: {request.capability_slug}")

    fb = Feedback(
        object_slug=request.capability_slug,
        action=FeedbackAction.REPORT_ISSUE,
        comment=request.model_dump_json(),
    )
    session.add(fb)
    await session.flush()
    await session.commit()
    return ContributionResponse(feedback_id=str(fb.id))


@router.post(
    "/contribute/adaptation",
    response_model=ContributionResponse,
    status_code=201,
)
async def submit_adaptation(
    request: AdaptationRequest,
    session: DBSession,
    workspace: PublicWorkspace,
) -> ContributionResponse:
    """Anonymous variant/adaptation submission. Stored as a `used_this`
    feedback row whose comment payload carries the variant fields."""
    if not await _slug_exists(session, workspace.id, request.capability_slug):
        raise HTTPException(status_code=404, detail=f"Unknown capability: {request.capability_slug}")

    fb = Feedback(
        object_slug=request.capability_slug,
        action=FeedbackAction.USED_THIS,
        comment=request.model_dump_json(),
    )
    session.add(fb)
    await session.flush()
    await session.commit()
    return ContributionResponse(feedback_id=str(fb.id))
