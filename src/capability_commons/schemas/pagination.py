from __future__ import annotations

import base64
import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    cursor: str | None = Field(None, description="Opaque cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Max items to return")

    def decode_cursor(self) -> uuid.UUID | None:
        if self.cursor is None:
            return None
        try:
            raw = base64.urlsafe_b64decode(self.cursor.encode()).decode()
            return uuid.UUID(raw)
        except (ValueError, Exception):
            return None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    total_count: int

    @staticmethod
    def encode_cursor(item_id: uuid.UUID) -> str:
        return base64.urlsafe_b64encode(str(item_id).encode()).decode()
