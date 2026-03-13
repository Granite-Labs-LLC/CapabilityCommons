from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from capability_commons.domain.enums import EdgeType, NodeKind, ProvenanceMethod, RelationStatus


class CreateEdgeRequest(BaseModel):
    workspace_id: uuid.UUID
    src_node_kind: NodeKind
    src_id: uuid.UUID
    edge_type: EdgeType
    dst_node_kind: NodeKind
    dst_id: uuid.UUID
    ordinal: int | None = None
    confidence: Decimal | float = Field(default=1.0, ge=0, le=1)
    provenance_method: ProvenanceMethod = ProvenanceMethod.HUMAN_AUTHORED
    status: RelationStatus = RelationStatus.CURRENT
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    src_node_kind: NodeKind
    src_id: uuid.UUID
    edge_type: EdgeType
    dst_node_kind: NodeKind
    dst_id: uuid.UUID
    ordinal: int | None = None
    confidence: Decimal | float
    provenance_method: ProvenanceMethod
    status: RelationStatus
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
