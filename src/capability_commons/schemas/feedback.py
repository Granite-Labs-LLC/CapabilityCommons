from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from capability_commons.domain.enums import FeedbackAction


class FeedbackRequest(BaseModel):
    action: FeedbackAction
    answer_id: str | None = None
    run_id: uuid.UUID | None = None
    object_slug: str | None = None
    comment: str | None = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    action: FeedbackAction
    created_at: datetime
