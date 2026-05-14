Read ./PLAN.md for initial context.

Done. I packaged the handoff into three files:

* [Developer blueprint (Markdown)](sandbox:/mnt/data/capability_commons_developer_blueprint.md)
* [Prioritized engineering backlog (XLSX)](sandbox:/mnt/data/capability_commons_engineering_backlog.xlsx)
* [Prioritized engineering backlog (CSV)](sandbox:/mnt/data/capability_commons_engineering_backlog.csv)

What’s in it:

* A build blueprint with target architecture, delivery phases, release gates, API contract direction, and team-lane recommendations.
* A prioritized backlog with 38 concrete tickets.
* File-level implementation targets for each ticket, plus proposed new files where needed.
* Dependencies, rough effort sizing, ownership lane, descriptions, and acceptance criteria.

A few key decisions are baked into the plan:

1. Keep the current Postgres/FastAPI/outbox foundation.
2. Treat `POST /v1/retrieve/evidence_pack` as the operator/evaluation surface.
3. Add a separate `POST /v1/public/ask` for normal users.
4. Build the missing public UI as a new `apps/site/` workspace, since the frontend is not present in the archive.
5. Make a real multi-source ingest run and a gold-query benchmark the release gates.

The implementation sequence in the blueprint is:

1. **Phase 0 — Correctness baseline**
   Fix ingestion correctness, provenance, graph semantics, publish/index flow, and access control.

2. **Phase 1 — Retrieval quality**
   Real hybrid retrieval, graph-aware rerank, implementation-field indexing, and evaluation harness.

3. **Phase 2 — Public answer layer**
   Structured implementation-ready answers, optional intent detection, conversation state, public workspace resolver.

4. **Phase 3 — Public interface**
   Guided ask, problem-first search, action cards, citation drawer, contradiction display, print/offline views.

5. **Phase 4 — Operational scale**
   Review queues, safety gates, analytics, caching, and launch runbooks.

The most important tickets to start with are:

* `ING-001` lifecycle casing normalization
* `ING-002` true page-preserving parse output
* `ING-003` globally unique segment IDs and lineage
* `ING-004` full canonical draft schema enforcement
* `SEED-001` edge import normalization
* `SEED-002` `EvidenceSpan` provenance persistence fix
* `PUB-001` route ingest-loaded publish through indexing/embedding
* `API-SEC-001` lock down retrieval run internals
* `SEARCH-001` real lexical + vector candidate union
* `RET-001` switch retrieval service to hybrid search

Recommended next move: use the backlog workbook as the planning source for Sprint 1 and assign Phase 0 across backend, data/ingest, and QA first.

