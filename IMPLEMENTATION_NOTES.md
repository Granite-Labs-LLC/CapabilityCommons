# Capability Commons Scaffold — Implementation Notes

## What is ready to use

- FastAPI app entrypoint in `src/capability_commons/main.py`
- async SQLAlchemy ORM models for the canonical v1 schema
- Alembic migration that executes the canonical SQL schema file
- Pydantic v2 request/response models for all v1 routes
- structured-data validators for the type-specific objects in the spec
- registry, entity, evidence, review, publication, search, graph, and retrieval service layers
- starter relational graph traversal and Postgres full-text search adapter
- retrieval-run persistence and evidence-pack rendering

## What is scaffolded but still needs production hardening

- object storage upload/download flows
- background outbox consumers for reindex/reprojection
- actual vector embedding generation and hybrid lexical+dense fusion
- robust authn/authz
- advanced contradiction clustering and reconciliation tooling
- bulk import pipelines and external connector sync jobs
- pagination and rate limiting on read-heavy endpoints

## Suggested first implementation tickets

1. Stand up Postgres with `pgvector`, run `alembic upgrade head`
2. Add real authentication / actor resolution
3. Build integration tests for object + version + publication flow
4. Add indexer trigger on publish via outbox consumer
5. Add workspace scoping / multi-tenant auth guards to every router
6. Replace lexical-only search with hybrid vector+fts reranking
7. Add export pipelines for printable module bundles
