# Tier 1-3 Sub-Projects: Testing, Audit, Storage — Design Spec

> **Scope:** Three independent sub-projects addressing TODO.md Tiers 1-3. Each gets its own implementation plan and can be built/shipped independently.

---

## Sub-project 1: Testing & Verification

### Goal

Validate the full stack with integration tests for every untested subsystem, plus API smoke tests for endpoint wiring.

### Architecture

Five new test files using the existing `db_session` + `workspace` fixtures from `tests/conftest.py`. No new test infrastructure. All integration tests run against a real Postgres (pgvector/pg16) in CI.

### Components

#### 1. `tests/test_integration_embedding.py` — Embedding pipeline E2E

Tests the publish → outbox → worker → segments → embeddings pipeline:

- Create object and version via `RegistryService`
- Publish version
- Verify `OutboxEvent` with type `version.published` exists
- Call `OutboxWorker._handle_version_published()` directly
- Verify `content_segments` rows created for the version
- Mock OpenAI, call `_handle_version_reindexed()`
- Verify embedding vectors are stored (non-NULL in segment rows)

#### 2. `tests/test_integration_retrieval.py` — Retrieval service E2E

Tests plan compilation → search → graph expand → evidence pack assembly:

- Seed 3-4 objects with edges and text content, publish and index them
- Call `RetrievalService.execute_plan()` with a query matching seeded content
- Verify evidence pack contains expected objects
- Verify graph expansion followed edges correctly
- Verify sufficiency scoring is reasonable
- Verify `RetrievalRun` record persisted with correct status

#### 3. `tests/test_integration_publication.py` — Publication service

Tests public rendering, graph data, and bundle assembly:

- Seed objects including a module with COVERS/ASSESSED_BY edges, publish all
- Test `list_published_objects()` returns correct count
- Test `build_graph_data()` includes correct nodes and edges
- Test `render_public_object(slug)` includes facets, entities, structured_data
- Test `render_module_bundle(slug)` returns structured sections
- Verify unpublished objects are excluded from all public methods

#### 4. `tests/test_integration_search.py` — Search adapter

Tests search indexing, ranking, and facet filtering:

- Seed and index objects with known distinct text content
- Test `search()` returns results ranked by relevance
- Test `fetch_segments()` returns correct segments for a version
- Test facet filtering: domain filter returns only matching objects
- Test that unpublished/unindexed objects do not appear in results

#### 5. `tests/test_smoke_api.py` — API endpoint smoke tests

Tests endpoint wiring across all 13 route modules:

- Use `TestClient(app)` with a dependency override providing a test API key
- Hit representative endpoints from each module: health, objects, edges, evidence, reviews, search, retrieval, public, ask, metrics, ingest, feedback
- Verify response status codes (200/201/401 as appropriate)
- Verify response bodies are valid JSON matching expected top-level keys
- No deep logic testing — just "does the wiring work"

### Data flow pattern

All integration tests follow the same pattern:

1. Use `db_session` + `workspace` fixtures from conftest
2. Create test data via `RegistryService` (objects, versions, edges)
3. Publish where needed via `RegistryService.publish_version()`
4. Index where needed via `VersionIndexer.reindex_version()`
5. Exercise the service under test
6. Assert results against known test data
7. Cleanup via conftest's `DELETE WHERE slug LIKE 'test-%'`

### Testing boundaries

- OpenAI embedding calls are always mocked (no real API key needed)
- Everything else uses a real Postgres — no mocked sessions
- Smoke tests use `TestClient(app)` with dependency override for auth
- CI runs these in the `integration` job alongside existing `test_integration.py`

---

## Sub-project 2: Audit Service

### Goal

Append-only event log for all significant state changes. Enables transparent governance history for objects, versions, edges, and reviews.

### Architecture

One new table, one new service, one new route module, plus integration calls from existing services.

### Database

**`audit_events` table:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK, server default |
| `workspace_id` | UUID | FK to workspaces |
| `event_type` | Enum | See enum below |
| `actor_key_id` | UUID | FK to api_keys, nullable (NULL for system/seed actions) |
| `target_object_id` | UUID | FK to context_objects, nullable |
| `target_version_id` | UUID | FK to context_object_versions, nullable |
| `target_edge_id` | UUID | FK to edges, nullable |
| `detail` | JSONB | Before/after diffs, contextual metadata |
| `created_at` | DateTime | server_default=now() |

**Indexes:**
- `idx_audit_workspace_created` on `(workspace_id, created_at DESC)` — timeline queries
- `idx_audit_object_created` on `(target_object_id, created_at DESC)` — per-object history

**`AuditEventType` enum:**
- `object_created`
- `version_created`
- `version_published`
- `version_deprecated`
- `edge_created`
- `edge_removed`
- `review_submitted`
- `object_edited`

### Service: `AuditService`

**File:** `src/capability_commons/audit/service.py`

Methods:
- `record_event(session, event_type, workspace_id, actor_key_id=None, target_object_id=None, target_version_id=None, target_edge_id=None, detail=None)` — append-only insert, returns the created event
- `get_object_history(session, object_id, limit=50, offset=0)` — returns events for one object, newest first
- `get_workspace_timeline(session, workspace_id, limit=50, offset=0, event_type=None)` — returns workspace-wide feed, optionally filtered by event type

### Integration points

Additive calls appended to existing service methods (no logic changes):

- **`RegistryService.create_object()`** → `audit.record_event("object_created", ...)`
- **`RegistryService.create_version()`** → `audit.record_event("version_created", ...)`
- **`RegistryService.publish_version()`** → `audit.record_event("version_published", ...)`
- **`RegistryService.deprecate_version()`** → `audit.record_event("version_deprecated", ...)`
- **`RegistryService.create_edge()`** → `audit.record_event("edge_created", ...)`
- **`ReviewService.submit_review()`** → `audit.record_event("review_submitted", ...)`

### API routes

**File:** `src/capability_commons/api/routes/audit.py`

- `GET /v1/audit/objects/{object_id}` — per-object history (authenticated, paginated)
- `GET /v1/audit/timeline` — workspace feed (authenticated, paginated, optional `?event_type=` filter)

### What it is NOT

- Not event sourcing or CDC — just an append-only log for human-readable history
- Not replacing the outbox — outbox drives side effects, audit is for governance
- No UI — API-only

---

## Sub-project 3: Storage Adapter + File Routes

### Goal

Enable file attachments (diagrams, photos, worksheets) on knowledge object versions. Local filesystem first, S3 interface stubbed for future.

### Architecture

Abstract adapter with local implementation, API routes for upload/download, wired to the existing `ObjectFile` model.

### Storage adapter

**File:** `src/capability_commons/storage/adapters.py`

**`StorageAdapter` ABC:**
- `put(key: str, data: bytes, media_type: str) -> None`
- `get(key: str) -> bytes`
- `delete(key: str) -> None`
- `exists(key: str) -> bool`

**`LocalStorageAdapter(StorageAdapter)`:**
- Stores files under configurable `STORAGE_ROOT` (default: `./data/files/`)
- Key maps to path: `{STORAGE_ROOT}/{key[:2]}/{key[2:4]}/{key}` (two-level hash prefix)
- Creates directories on `put()` if they don't exist
- Raises `FileNotFoundError` on `get()` / `delete()` if missing

**`S3StorageAdapter(StorageAdapter)`:**
- Stub only — all methods raise `NotImplementedError("S3 adapter not yet implemented")`
- Class exists with docstrings for future implementation

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `STORAGE_BACKEND` | `"local"` | Which adapter to use (`"local"` or `"s3"`) |
| `STORAGE_ROOT` | `./data/files` | Local filesystem path |
| `STORAGE_MAX_FILE_SIZE` | `52428800` (50MB) | Max upload size in bytes |

**Allowed media types:** `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml`, `application/pdf`, `text/plain`, `text/markdown`, `text/csv`

### API routes

**File:** `src/capability_commons/api/routes/files.py`

**Prefix:** `/v1/objects/{object_id}/versions/{version_id}/files`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/` | Multipart upload. Computes SHA-256 checksum, generates UUID key, stores via adapter, creates `ObjectFile` row. Returns file metadata (201). |
| `GET` | `/` | List files attached to a version. Returns array of file metadata. |
| `GET` | `/{file_id}` | Download file. Returns `StreamingResponse` with correct `Content-Type`. |
| `DELETE` | `/{file_id}` | Remove file from storage + delete DB row (204). |

All routes require API key authentication.

### Schemas

**`FileMetadataResponse`:**
- `id` (UUID), `object_store_key` (str), `media_type` (str), `byte_size` (int | None), `checksum` (str | None), `label` (str | None), `created_at` (datetime)

### Validation

- File size checked against `STORAGE_MAX_FILE_SIZE` before storing (413 if exceeded)
- Media type checked against allowlist (415 if not allowed)
- SHA-256 checksum computed and stored for integrity verification

### Dependency injection

A `get_storage_adapter()` dependency that reads `STORAGE_BACKEND` from config and returns the appropriate adapter instance. Injected into route handlers via `Depends()`.

### What it is NOT

- Not a CDN — direct file serving, no caching layer
- S3 is a stub — local filesystem is the full implementation
- No public file access — all routes require authentication
- No image processing — files stored as-is

---

## Execution order

1. **Testing & Verification** — first, because it validates existing code before we add more
2. **Audit Service** — second, clean isolated scope, governance value
3. **Storage Adapter** — third, builds on patterns established in #2

Each sub-project gets its own implementation plan via the writing-plans skill.

## Out of scope

These Tier 1-3 items are NOT covered by this spec:

- **Operational tasks** (secret management, first ingestion run, search tuning, citation review) — documented in `docs/OPERATIONAL_TASKS.md`, require human judgment
- **Schema documentation / public API guide** — separate documentation effort
- **Neo4j/OpenSearch adapters** — scale infrastructure, not needed yet
- **Read replicas** — infrastructure config, not application code
- **Offline export / print field guides** — separate sub-project when content exists
- **Community workflows** (attribution, adaptation, field testing, translation) — need process design input before code
- **Embedding backfill job** — small standalone task, can be added to any plan
- **Contradiction detection pipeline** — depends on content volume, premature now
