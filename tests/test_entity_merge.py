"""Tests for EntityService.merge_entities downstream relation remapping."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from capability_commons.domain.enums import EntityStatus, EntityType
from capability_commons.services.entities import EntityService
from capability_commons.services.exceptions import ConflictError


def _make_entity(
    entity_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    status: EntityStatus = EntityStatus.ACTIVE,
) -> MagicMock:
    entity = MagicMock()
    entity.id = entity_id
    entity.status = status
    entity.entity_type = EntityType.TOPIC
    entity.canonical_name = f"entity-{entity_id}"
    entity.workspace_id = workspace_id or uuid.uuid4()
    return entity


@pytest.fixture
def workspace_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def source_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def target_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_merge_entities_remaps_relations(
    source_id: uuid.UUID, target_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    source = _make_entity(source_id, workspace_id=workspace_id)
    target = _make_entity(target_id, workspace_id=workspace_id)

    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    with (
        patch(
            "capability_commons.services.entities.get_entity",
            side_effect=lambda _s, eid: source if eid == source_id else target,
        ),
        patch(
            "capability_commons.services.entities.add_outbox_event",
            new_callable=AsyncMock,
        ) as mock_outbox,
    ):
        svc = EntityService(session)
        result = await svc.merge_entities(source_id, target_id)

    # Source marked as MERGED
    assert source.status == EntityStatus.MERGED

    # Outbox event emitted with correct type
    mock_outbox.assert_awaited_once()
    _, kwargs = mock_outbox.call_args
    assert kwargs["event_type"] == "entity.merged"

    # Returns target
    assert result is target


@pytest.mark.asyncio
async def test_merge_already_merged_source_raises(
    source_id: uuid.UUID, target_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    source = _make_entity(source_id, workspace_id=workspace_id, status=EntityStatus.MERGED)
    target = _make_entity(target_id, workspace_id=workspace_id, status=EntityStatus.ACTIVE)

    session = AsyncMock()

    with patch(
        "capability_commons.services.entities.get_entity",
        side_effect=lambda _s, eid: source if eid == source_id else target,
    ):
        svc = EntityService(session)
        with pytest.raises(ConflictError, match="already merged"):
            await svc.merge_entities(source_id, target_id)


@pytest.mark.asyncio
async def test_merge_already_merged_target_raises(
    source_id: uuid.UUID, target_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    source = _make_entity(source_id, workspace_id=workspace_id, status=EntityStatus.ACTIVE)
    target = _make_entity(target_id, workspace_id=workspace_id, status=EntityStatus.MERGED)

    session = AsyncMock()

    with patch(
        "capability_commons.services.entities.get_entity",
        side_effect=lambda _s, eid: source if eid == source_id else target,
    ):
        svc = EntityService(session)
        with pytest.raises(ConflictError, match="has already been merged away"):
            await svc.merge_entities(source_id, target_id)


@pytest.mark.asyncio
async def test_merge_entities_same_id_raises() -> None:
    session = AsyncMock()
    svc = EntityService(session)
    same_id = uuid.uuid4()

    with pytest.raises(ConflictError, match="must differ"):
        await svc.merge_entities(same_id, same_id)


@pytest.mark.asyncio
async def test_merge_cross_workspace_raises(source_id: uuid.UUID, target_id: uuid.UUID) -> None:
    source = _make_entity(source_id, workspace_id=uuid.uuid4())
    target = _make_entity(target_id, workspace_id=uuid.uuid4())

    session = AsyncMock()

    with patch(
        "capability_commons.services.entities.get_entity",
        side_effect=lambda _s, eid: source if eid == source_id else target,
    ):
        svc = EntityService(session)
        with pytest.raises(ConflictError, match="different workspaces"):
            await svc.merge_entities(source_id, target_id)
