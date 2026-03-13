# Production Readiness v1.0 — Design Document

**Goal:** Close the operational infrastructure gaps identified in the gap analysis to make Capability Commons production-ready.

**Date:** 2026-03-13

---

## 1. Outbox Event Consumer

A simple async worker that polls `outbox_events` for unprocessed rows and dispatches handlers:
- `version.published` → triggers reindexing via `VersionIndexer`
- `version.published` → enqueues embedding generation
- Polling loop with configurable interval (default 2s)
- Runs as a separate process: `python -m capability_commons.cli.worker`
- No Celery/Redis dependency — just asyncio + the existing Postgres connection

## 2. Auth: API Key + Workspace Scoping

- New `api_keys` table: `id`, `workspace_id`, `key_hash` (SHA-256), `name`, `created_at`, `revoked_at`
- `Authorization: Bearer <key>` header → middleware looks up hash, resolves workspace
- FastAPI dependency `get_current_workspace()` replaces optional `ActorID`
- Public read routes (`/public/*`) remain unauthenticated
- CLI command to create/revoke keys: `python -m capability_commons.cli.keys`
- Alembic migration for the new table

## 3. Integration Tests

End-to-end flows using a real test database (pytest fixtures with transaction rollback):
- **Object lifecycle**: create → version → publish → verify current_version set
- **Search**: publish object → reindex → search by term → find it
- **Graph**: create objects + edges → traverse neighbors → verify paths
- **Evidence + Review**: create source → attach span → submit review → check lifecycle transition
- **Retrieval**: seed objects → execute plan → verify evidence pack structure
- **Seed idempotency**: run seed twice → assert no duplicates

## 4. Embedding Pipeline

- `EmbeddingProvider` interface: `async def embed(texts: list[str]) -> list[list[float]]`
- `OpenAIEmbeddingProvider`: calls `text-embedding-3-small`, respects `EMBEDDING_DIM`, batches up to 100 texts
- New config vars: `OPENAI_API_KEY`, `EMBEDDING_MODEL` (default `text-embedding-3-small`), `EMBEDDING_BATCH_SIZE` (default 50)
- `EmbeddingService.embed_version(version_id)`: fetches segments, calls provider, writes vectors
- Outbox consumer triggers embedding after reindex
- Search adapter gains hybrid mode: `(0.7 * fts_score) + (0.3 * cosine_similarity)` when vectors available, falls back to FTS-only when not

## 5. Entity Merge Completion

- `EntityService.merge_entities()` already marks source as MERGED
- Add: remap `context_object_entities`, `edges` (where entity is src/dst), and `entity_aliases` from source → target entity
- Wrap in a single transaction

## 6. Cursor Pagination

- `PaginationParams` schema: `cursor` (optional opaque string, base64-encoded UUID), `limit` (default 20, max 100)
- `PaginatedResponse[T]`: `items`, `next_cursor`, `total_count`
- Applied to: `GET /objects` (list), `POST /search`, `GET /retrieval_runs`
- Cursor is the last item's ID, keyset pagination (not OFFSET)

## 7. Rate Limiting

- Simple sliding-window rate limiter using Postgres (no Redis needed)
- `rate_limit_log` table: `api_key_id`, `window_start`, `request_count`
- Default: 100 requests/minute per API key
- FastAPI middleware checks before route execution
- `429 Too Many Requests` with `Retry-After` header
- Public routes get IP-based limiting (more generous, 300/min)

---

## Out of Scope (YAGNI)

- No OAuth/JWT (bolt on later)
- No Neo4j or OpenSearch adapters (v2)
- No static PDF export (v2)
- No bulk import beyond seed CLI (v2)
- No contradiction auto-clustering (v2)

## Implementation Order

1. Entity merge completion (small, self-contained)
2. API key auth + workspace scoping (migration + middleware + CLI)
3. Cursor pagination (schemas + route changes)
4. Rate limiting (middleware + migration)
5. Outbox event consumer (worker process)
6. Embedding pipeline (provider interface + OpenAI adapter + service)
7. Integration tests (validates everything above)
