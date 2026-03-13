from __future__ import annotations

import uuid

from sqlalchemy import join, select
from sqlalchemy.ext.asyncio import AsyncSession

from capability_commons.db.models import Edge, EdgeEvidenceSpan, EvidenceSource, EvidenceSpan
from capability_commons.services.exceptions import ConflictError
from capability_commons.services.helpers import add_outbox_event, get_version


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_source(
        self,
        *,
        workspace_id: uuid.UUID,
        source_kind,
        title: str,
        uri: str | None = None,
        citation_text: str | None = None,
        trust_tier=None,
        license: str | None = None,
        language_code: str = "en",
        metadata: dict | None = None,
        created_by: uuid.UUID | None = None,
    ) -> EvidenceSource:
        source = EvidenceSource(
            workspace_id=workspace_id,
            source_kind=source_kind,
            title=title,
            uri=uri,
            citation_text=citation_text,
            trust_tier=trust_tier,
            license=license,
            language_code=language_code,
            metadata_json=metadata or {},
            created_by=created_by,
        )
        self.session.add(source)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="evidence_source",
            aggregate_id=source.id,
            event_type="evidence.source_created",
            payload={"source_id": str(source.id), "workspace_id": str(workspace_id)},
        )
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def create_span(
        self,
        *,
        source_id: uuid.UUID,
        context_object_version_id: uuid.UUID | None,
        segment_id: uuid.UUID | None,
        start_char: int,
        end_char: int,
        excerpt: str,
        checksum: str | None = None,
    ) -> EvidenceSpan:
        source = await self.session.get(EvidenceSource, source_id)
        if source is None:
            raise ConflictError(f"Evidence source {source_id} does not exist")
        if context_object_version_id is not None:
            await get_version(self.session, context_object_version_id)
        span = EvidenceSpan(
            source_id=source_id,
            context_object_version_id=context_object_version_id,
            segment_id=segment_id,
            start_char=start_char,
            end_char=end_char,
            excerpt=excerpt,
            checksum=checksum,
        )
        self.session.add(span)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="evidence_span",
            aggregate_id=span.id,
            event_type="evidence.span_created",
            payload={"source_id": str(source.id), "span_id": str(span.id)},
        )
        await self.session.commit()
        await self.session.refresh(span)
        return span

    async def attach_span_to_edge(self, edge_id: uuid.UUID, evidence_span_id: uuid.UUID) -> EdgeEvidenceSpan:
        edge = await self.session.get(Edge, edge_id)
        if edge is None:
            raise ConflictError(f"Edge {edge_id} does not exist")
        span = await self.session.get(EvidenceSpan, evidence_span_id)
        if span is None:
            raise ConflictError(f"Evidence span {evidence_span_id} does not exist")
        existing = await self.session.get(EdgeEvidenceSpan, {"edge_id": edge_id, "evidence_span_id": evidence_span_id})
        if existing is not None:
            return existing
        link = EdgeEvidenceSpan(edge_id=edge_id, evidence_span_id=evidence_span_id)
        self.session.add(link)
        await self.session.flush()
        await add_outbox_event(
            self.session,
            aggregate_type="edge",
            aggregate_id=edge.id,
            event_type="edge.citation_attached",
            payload={"edge_id": str(edge.id), "evidence_span_id": str(span.id)},
        )
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def list_citations_for_version(self, version_id: uuid.UUID) -> list[dict]:
        await get_version(self.session, version_id)
        stmt = (
            select(EvidenceSpan.id, EvidenceSource.id, EvidenceSource.title, EvidenceSource.uri, EvidenceSpan.excerpt, EvidenceSpan.start_char, EvidenceSpan.end_char)
            .select_from(join(EvidenceSpan, EvidenceSource, EvidenceSpan.source_id == EvidenceSource.id))
            .where(EvidenceSpan.context_object_version_id == version_id)
            .order_by(EvidenceSource.title.asc(), EvidenceSpan.start_char.asc())
        )
        result = await self.session.execute(stmt)
        citations = []
        for span_id, source_id, source_title, uri, excerpt, start_char, end_char in result.all():
            citations.append(
                {
                    "evidence_span_id": span_id,
                    "source_id": source_id,
                    "source_title": source_title,
                    "uri": uri,
                    "excerpt": excerpt,
                    "start_char": start_char,
                    "end_char": end_char,
                }
            )
        return citations
