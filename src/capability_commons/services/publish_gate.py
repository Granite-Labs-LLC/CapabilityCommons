"""Publish gate — rule-based checks that must pass before a version can be published.

Blocks publishing when:
- High-risk content (risk_band HIGH/EXPERT_ONLY) lacks an explicit APPROVED review
- Required safety_boundary is missing from structured_data on types that need it
- Unresolved contradictions reference the version
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import (
    ContradictionCase,
    ContextObjectVersion,
    ReviewRecord,
)
from capability_commons.domain.enums import (
    COType,
    ContradictionStatus,
    ReviewOutcome,
    RiskBand,
)

# Types that require a safety_boundary field in structured_data
SAFETY_BOUNDARY_REQUIRED_TYPES = {
    COType.SKILL_GUIDE,
    COType.PROJECT_BLUEPRINT,
    COType.LOCAL_ADAPTATION,
}

# Risk bands that require explicit review approval before publishing
HIGH_RISK_BANDS = {RiskBand.HIGH, RiskBand.EXPERT_ONLY}


@dataclass
class GateResult:
    """Result of a publish gate check."""
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PublishGate:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check(self, version: ContextObjectVersion, object_type: COType) -> GateResult:
        """Run all publish gate checks and return the result."""
        blockers: list[str] = []
        warnings: list[str] = []

        # 1. High-risk review gate
        if version.risk_band in HIGH_RISK_BANDS:
            has_approval = await self._has_approved_review(version.id)
            if not has_approval:
                blockers.append(
                    f"Risk band '{version.risk_band.value}' requires an approved review before publishing"
                )

        # 2. Safety boundary gate
        if object_type in SAFETY_BOUNDARY_REQUIRED_TYPES:
            sd = version.structured_data or {}
            has_safety = bool(sd.get("safety_boundary"))
            # Also check in implementation_profile
            profile = sd.get("implementation_profile", {}) or {}
            has_escalation = bool(profile.get("escalation_guidance"))
            if not has_safety and not has_escalation:
                blockers.append(
                    f"Type '{object_type.value}' requires a safety_boundary or escalation_guidance"
                )

        # 3. Unresolved contradictions gate
        open_count = await self._count_open_contradictions(version.id)
        if open_count > 0:
            blockers.append(
                f"{open_count} unresolved contradiction(s) must be resolved before publishing"
            )

        # Advisory warnings (don't block)
        if not version.summary_short:
            warnings.append("Missing summary_short — recommended for search quality")

        return GateResult(
            passed=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
        )

    async def _has_approved_review(self, version_id: uuid.UUID) -> bool:
        """Check if the version has at least one APPROVED review."""
        result = await self.session.scalar(
            select(func.count()).where(
                ReviewRecord.context_object_version_id == version_id,
                ReviewRecord.outcome == ReviewOutcome.APPROVED,
            )
        )
        return (result or 0) > 0

    async def _count_open_contradictions(self, version_id: uuid.UUID) -> int:
        """Count unresolved contradictions involving this version."""
        result = await self.session.scalar(
            select(func.count()).where(
                (ContradictionCase.left_version_id == version_id)
                | (ContradictionCase.right_version_id == version_id),
                ContradictionCase.status.in_([
                    ContradictionStatus.OPEN,
                    ContradictionStatus.TRIAGED,
                ]),
            )
        )
        return result or 0
