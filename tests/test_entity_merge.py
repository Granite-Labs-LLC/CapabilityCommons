"""Tests for EntityService.merge_entities downstream relation remapping."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from capability_commons.domain.enums import EntityStatus, EntityType
from capability_commons.services.entities import EntityService


def _make_entity(entity_id: uuid.UUID, status: EntityStatus = EntityStatus.ACTIVE) -> MagicMock:
    entity = MagicMock()
    entity.id = entity_id
    entity.status = status
    entity.entity_type = EntityType.TOPIC
    entity.canonical_name = f"entity-{entity_id}"
    return entity


@pytest.fixture
def source_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def target_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_merge_entities_remaps_relations(source_id: uuid.UUID, target_id: uuid.UUID) -> None:
    source = _make_entity(source_id)
    target = _make_entity(target_id)

    session = AsyncMock()
    session.execute = AsyncMock()
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

    # 5 execute calls: alias update, COE delete duplicates, COE remap, edge src, edge dst
    assert session.execute.await_count == 5

    # Source marked as MERGED
    assert source.status == EntityStatus.MERGED

    # Outbox event emitted with correct type
    mock_outbox.assert_awaited_once()
    call_kwargs = mock_outbox.call_args
    assert call_kwargs[1]["event_type"] == "entity.merged" or call_kwargs[0][3] == "entity.merged"

    # Returns target
    assert result is target


@pytest.mark.asyncio
async def test_merge_entities_same_id_raises() -> None:
    session = AsyncMock()
    svc = EntityService(session)
    same_id = uuid.uuid4()

    from capability_commons.services.exceptions import ConflictError

    with pytest.raises(ConflictError, match="must differ"):
        await svc.merge_entities(same_id, same_id)
