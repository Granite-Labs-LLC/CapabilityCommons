from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContradictionCase, ReviewRecord
from capability_commons.domain.enums import LifecycleState, ReviewOutcome, ValidityStatus
from capability_commons.services.exceptions import ConflictError
from capability_commons.services.helpers import add_outbox_event, get_object, get_version
from capability_commons.services.registry import RegistryService


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.registry = RegistryService(session)

    async def submit_review(
        self,
        *,
        workspace_id: uuid.UUID,
        context_object_version_id: uuid.UUID,
        review_type,
        outcome,
        reviewer_id: uuid.UUID | None = None,
        commentary: str | None = None,
        checklist: dict | None = None,
    ) -> ReviewRecord:
        version = await get_version(self.session, context_object_version_id)
        review = ReviewRecord(
            workspace_id=workspace_id,
            context_object_version_id=context_object_version_id,
            review_type=review_type,
            outcome=outcome,
            reviewer_id=reviewer_id,
            commentary=commentary,
            checklist=checklist or {},
        )
        self.session.add(review)
        if outcome == ReviewOutcome.APPROVED:
            version.context_object.lifecycle_state = LifecycleState.REVIEWED
        elif outcome == ReviewOutcome.VERIFIED:
            version.context_object.lifecycle_state = LifecycleState.VERIFIED
        elif outcome == ReviewOutcome.DEPRECATED:
            version.validity_status = ValidityStatus.DEPRECATED
            version.context_object.lifecycle_state = LifecycleState.DEPRECATED
        elif outcome == ReviewOutcome.DISPUTED:
            version.validity_status = ValidityStatus.DISPUTED
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="review_record",
            aggregate_id=review.id,
            event_type="review.submitted",
            payload={"version_id": str(context_object_version_id), "outcome": outcome.value},
        )
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def open_contradiction(
        self,
        *,
        workspace_id: uuid.UUID,
        left_version_id: uuid.UUID,
        right_version_id: uuid.UUID,
        dimension,
        severity,
        opened_by: uuid.UUID | None = None,
    ) -> ContradictionCase:
        if left_version_id == right_version_id:
            raise ConflictError("Contradiction requires two distinct versions")
        await get_version(self.session, left_version_id)
        await get_version(self.session, right_version_id)
        contradiction = ContradictionCase(
            workspace_id=workspace_id,
            left_version_id=left_version_id,
            right_version_id=right_version_id,
            dimension=dimension,
            severity=severity,
            opened_by=opened_by,
        )
        self.session.add(contradiction)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="contradiction_case",
            aggregate_id=contradiction.id,
            event_type="contradiction.opened",
            payload={
                "left_version_id": str(left_version_id),
                "right_version_id": str(right_version_id),
                "dimension": dimension.value,
            },
        )
        await self.session.commit()
        await self.session.refresh(contradiction)
        return contradiction

    async def resolve_contradiction(
        self,
        contradiction_id: uuid.UUID,
        *,
        resolved_by: uuid.UUID | None,
        resolution_note: str,
        resolution_version_id: uuid.UUID | None,
        status,
    ) -> ContradictionCase:
        contradiction = await self.session.get(ContradictionCase, contradiction_id)
        if contradiction is None:
            raise ConflictError(f"Contradiction {contradiction_id} does not exist")
        if resolution_version_id is not None:
            await get_version(self.session, resolution_version_id)
        contradiction.resolved_by = resolved_by
        contradiction.resolved_at = datetime.now(timezone.utc)
        contradiction.resolution_note = resolution_note
        contradiction.resolution_version_id = resolution_version_id
        contradiction.status = status
        await add_outbox_event(
            self.session,
            aggregate_type="contradiction_case",
            aggregate_id=contradiction.id,
            event_type="contradiction.resolved",
            payload={"contradiction_id": str(contradiction.id), "status": status.value},
        )
        await self.session.commit()
        await self.session.refresh(contradiction)
        return contradiction

    async def mark_verified(self, object_id: uuid.UUID, version_id: uuid.UUID) -> None:
        obj = await get_object(self.session, object_id)
        version = await get_version(self.session, version_id)
        if version.context_object_id != obj.id:
            raise ConflictError("Version does not belong to object")
        obj.lifecycle_state = LifecycleState.VERIFIED
        await self.session.commit()

    async def mark_disputed(self, object_id: uuid.UUID, version_id: uuid.UUID) -> None:
        await self.registry.mark_version_validity(object_id, version_id, ValidityStatus.DISPUTED)

    async def propose_deprecation(self, object_id: uuid.UUID, version_id: uuid.UUID) -> None:
        await self.registry.mark_version_validity(object_id, version_id, ValidityStatus.DEPRECATED)
