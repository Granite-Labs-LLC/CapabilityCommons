
# Capability Commons — Implementation Checklist

## Phase 1: Core registry
- [ ] Create Postgres enums and tables from `capability_commons_agentic_data_lite_schema.sql`
- [ ] Implement `RegistryService`
- [ ] Implement object/version CRUD endpoints
- [ ] Implement type-specific `structured_data` validators
- [ ] Implement facet and entity attachment endpoints
- [ ] Implement edge creation endpoint with service-layer invariants
- [ ] Implement publication lifecycle transitions
- [ ] Emit outbox events on create/publish/update

## Phase 2: Search and graph
- [ ] Implement `content_segments` chunking pipeline
- [ ] Add `pgvector` embeddings and Postgres FTS
- [ ] Implement `PostgresSearchAdapter`
- [ ] Implement `RelationalGraphAdapter` using recursive CTEs
- [ ] Add prerequisite, ordered membership, and supersession traversal queries

## Phase 3: Evidence and review
- [ ] Implement `EvidenceService`
- [ ] Implement `ReviewService`
- [ ] Add contradiction creation/resolution flows
- [ ] Add verification/dispute/deprecate endpoints
- [ ] Surface citations and contradiction banners in publication views

## Phase 4: Retrieval
- [ ] Implement `TaskSpec`
- [ ] Implement intent-specific plan compiler
- [ ] Implement iterative execution loop
- [ ] Implement reranking and sufficiency scoring
- [ ] Persist retrieval runs and retrieval steps
- [ ] Render `EvidencePack` as JSON and Markdown

## Phase 5: Publication
- [ ] Implement public read endpoints for objects, modules, and learning paths
- [ ] Render prerequisites, next steps, citations, and applicability facets
- [ ] Render teach-forward packet pages
- [ ] Add printable/static export support

## Optional Phase 6: Projection adapters
- [ ] Implement `OpenSearchSearchAdapter`
- [ ] Implement `Neo4jGraphAdapter`
- [ ] Implement outbox-driven projection sync jobs
- [ ] Add rebuild/reindex operational tooling
