from __future__ import annotations

import re
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import ContentSegment
from capability_commons.services.helpers import add_outbox_event, get_version


def chunk_text(text: str, max_chars: int = 900, overlap: int = 150) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph
        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap :]
    if current:
        chunks.append(current)
    return chunks


class VersionIndexer:
    def __init__(self, session: AsyncSession, embedding_dim: int = 1536) -> None:
        self.session = session
        self.embedding_dim = embedding_dim

    async def reindex_version(self, version_id: uuid.UUID) -> list[ContentSegment]:
        version = await get_version(self.session, version_id)
        await self.session.execute(
            delete(ContentSegment).where(ContentSegment.context_object_version_id == version_id)
        )
        chunks = chunk_text(version.markdown_body or version.plain_language)
        rows: list[ContentSegment] = []
        for ordinal, chunk in enumerate(chunks):
            row = ContentSegment(
                workspace_id=version.context_object.workspace_id,
                context_object_version_id=version.id,
                ordinal=ordinal,
                text_content=chunk,
                token_count=len(chunk.split()),
                embedding=None,
                metadata_json={"strategy": "paragraph_overlap", "embedding_status": "pending"},
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="context_object_version",
            aggregate_id=version.id,
            event_type="version.reindexed",
            payload={"version_id": str(version.id), "segment_count": len(rows)},
        )
        await self.session.commit()
        return rows
