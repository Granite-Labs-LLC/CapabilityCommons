# Capability Commons — Project Status

Last updated: 2026-03-25

## Overview

Capability Commons is a working, deployable knowledge platform. The backend API, database schema, seed data, ingestion pipeline, and frontend site are all implemented and functional. The system can be stood up with Docker Compose, seeded with the starter knowledge graph, and queried through both API endpoints and the Astro frontend.

The project has completed its initial production-hardening phase: CI/CD, structured logging, error tracking, metrics, connection pooling, migration safety, auth improvements, and Swagger UI are all in place. The focus now shifts to content population (first real ingestion run), operational deployment, and community tooling.

## Codebase metrics

| Metric | Count |
|--------|-------|
| Python source files | 82 |
| Python source lines | ~7,500 |
| Test files | 24 |
| Test lines | ~2,100 |
| Collected tests | 130 |
| Passing tests | 127 (3 require live Postgres) |
| API endpoints | 37 |
| Database tables | 19 |
| Alembic migrations | 5 |
| Seeded objects | 49 (25 capability + 12 modules + 12 assessments) |
| Seeded edges | 175 |
| Enum types | 30+ |

## Component status

### Backend API — Complete

FastAPI application with 37 endpoints across 9 route modules. All routes are wired, return valid response models, and enforce authentication.

| Route module | Endpoints | Status |
|-------------|-----------|--------|
| Health | 2 (`/health`, `/health/detailed`) | Production-ready |
| Objects | 6 (CRUD, versioning, publish, facets) | Production-ready |
| Entities | 2 (create, add aliases) | Production-ready |
| Edges | 2 (create, list with filters) | Production-ready |
| Evidence | 4 (sources, spans, edge citations, version citations) | Production-ready, tested |
| Reviews | 6 (submit, contradictions, resolve, verify, dispute, deprecate) | Production-ready, tested |
| Search | 1 (hybrid FTS + embedding) | Production-ready |
| Retrieval | 3 (evidence pack, run details, steps) | Production-ready |
| Public | 7 (published objects, graph, bundles, paths) | Production-ready |

**Middleware:** Structured request logging (structlog), rate limiting (per-key sliding window), CORS, API key authentication (with expiry support), Prometheus metrics.

**API documentation:** Swagger UI at `/docs`, ReDoc at `/redoc`.

### Observability — Complete

| Component | Implementation | Status |
|-----------|---------------|--------|
| Structured logging | structlog — JSON in production, colored console in dev | Production-ready |
| Error tracking | Sentry (opt-in via `SENTRY_DSN` env var) | Production-ready |
| Request metrics | Prometheus at `/metrics` (opt-out via `METRICS_ENABLED=false`) | Production-ready |
| Health checks | `/health/detailed` — DB connectivity, migration heads, embedding status | Production-ready |
| Migration safety | Startup warning if pending Alembic migrations detected | Production-ready |

### Database — Complete

PostgreSQL 16 with pgvector. 19 tables with comprehensive constraints, 40+ indexes, and full relationship mapping.

| Table group | Tables | Status |
|------------|--------|--------|
| Core objects | `workspaces`, `context_objects`, `context_object_versions`, `context_object_facets` | Production-ready |
| Entities | `entities`, `entity_aliases`, `context_object_entities` | Production-ready |
| Graph | `edges`, `edge_evidence_spans` | Production-ready |
| Evidence | `evidence_sources`, `evidence_spans` | Production-ready |
| Reviews | `review_records`, `contradiction_cases` | Production-ready |
| Search | `content_segments` (pgvector 1536-dim, IVFFLAT index) | Production-ready |
| Retrieval | `retrieval_runs`, `retrieval_steps` | Production-ready |
| Infrastructure | `api_keys` (with `expire_at`), `rate_limit_log`, `outbox_events`, `object_files` | Production-ready |

**Migrations:** 5 applied (initial schema, API keys, lifecycle index, evidence external_id, API key expire_at).

**Connection pooling:** Configurable via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_PRE_PING` env vars.

### Services layer — Complete

| Service | Purpose | Status |
|---------|---------|--------|
| `RegistryService` | Object/version/edge CRUD, publish workflow | Fully implemented |
| `EntityService` | Entity creation, aliasing, merging | Fully implemented |
| `EvidenceService` | Source/span creation, edge attachment | Fully implemented |
| `EmbeddingService` | OpenAI embeddings, segment indexing | Fully implemented (feature-gated on API key) |
| `ReviewService` | Review submission, contradiction handling | Fully implemented |
| `RetrievalService` | Plan compilation, execution, evidence pack assembly | Fully implemented |
| `PublicationService` | Rendering public objects, bundles, graphs, paths | Fully implemented |
| `RetrievalPlanner` | Intent-to-edge-type mapping (9 intents, 25 edge types) | Fully implemented |

### Search and graph adapters — Partial

| Adapter | Implementation | Status |
|---------|---------------|--------|
| `PostgresSearchAdapter` | Full-text search + embedding hybrid | Production-ready |
| `RelationalGraphAdapter` | SQL BFS for neighbors, paths, prerequisites, members | Production-ready |
| `Neo4jGraphAdapter` | Planned extension point | Not started |
| `OpenSearchAdapter` | Planned extension point | Not started |

Abstract base classes exist for both `SearchAdapter` and `GraphAdapter` (4 methods each). The Postgres/relational implementations cover all methods. Neo4j and OpenSearch are documented as future extension points for scale.

### CLI tools — Complete

| Tool | Command | Status |
|------|---------|--------|
| Seed loader | `python -m capability_commons.cli` | Production-ready, idempotent |
| API key manager | `python -m capability_commons.cli.keys` | Production-ready (create, revoke, rotate, list) |
| Outbox worker | `python -m capability_commons.cli.worker` | Functional |
| Ingestion pipeline | `python -m capability_commons.cli.ingest` | Complete (11 commands) |

### Ingestion pipeline — Complete

8-pass LLM-assisted pipeline for converting source documents into knowledge objects.

| Pass | Command | Input | Output | Status |
|------|---------|-------|--------|--------|
| 0 | `parse` | PDF | Segments JSONL | Complete |
| 1 | `extract` | Segments | Extraction matrix CSV | Complete |
| 2 | `draft` | Matrix + segments | YAML objects | Complete |
| 3 | `cite` | YAML + segments | Citations in YAML | Complete |
| 4 | `canonicalize` | YAML objects | Deduplicated YAML | Complete |
| 5 | `edges` | Objects | Edges CSV | Complete |
| 6 | `bundles` | Objects | Six-part bundles in YAML | Complete |
| 7 | `load` | YAML + edges | Database records | Complete |
| — | `validate` | YAML + edges | Error/warning report | Complete |
| — | `status` | Manifest | Pass completion table | Complete |
| — | `init` | Source file | Project directory | Complete |

All passes have unit tests with mocked LLM responses. The pipeline has been designed for external contributors to submit ingestion projects via PR.

### Seed data — Complete

Two seed packs loaded on startup:

**Capability nodes** (25 objects across 7 domains): water, food, shelter, power, repair, gardening, epistemics. Each with full YAML including title, plain_language, markdown_body, structured_data, prerequisites, and suggested_edges.

**Curriculum nodes** (24 objects): 12 weekly modules + 12 assessments with COVERS, ASSESSED_BY, and PRECEDES edges linking them to capability nodes.

**Total seeded:** 49 context objects, 49 versions, 175 edges. Loader is idempotent.

### CI/CD — Configured

| Component | Status |
|-----------|--------|
| GitHub Actions CI | Configured (lint, typecheck, test, integration, Docker build) |
| Linting | ruff (E, F, I, W rules) |
| Type checking | mypy (incremental adoption, ignore_missing_imports) |
| Integration tests | pgvector/pgvector:pg16 service in CI |
| Docker build | Verified in CI |
| Deploy pipeline | **Not configured** |
| Kubernetes | **Not started** |

### Deployment — Functional

| Component | Status |
|-----------|--------|
| Dockerfile | Production-ready (slim Python 3.14 image, port 8100) |
| docker-compose.yml | Functional (pgvector + API, healthchecks) |
| `.env.example` | 27+ settings documented |
| Alembic migrations | 5 applied, auto-generate works |
| Cloud deployment docs | Linux production guide exists |

### Frontend (CapabilityCommonsSite) — Functional

Astro 5 + React 19 static site consuming the backend API.

| Feature | Status |
|---------|--------|
| Landing page | Complete |
| Object explorer | Complete (search, filter by domain/stage/difficulty) |
| Object detail pages | Complete (structured payload, prerequisites, citations) |
| Graph visualization | Complete (D3-based interactive explorer) |
| Search | Complete (connected to backend hybrid search) |
| Learning paths | Complete |
| Syllabus / modules | Complete |
| AI tutor (AskTutor) | Complete (connected to retrieval API) |
| Bundle viewer | Complete (six-part display) |
| Ring explorer | Complete (concentric ring entry model) |
| Offline mode | Page exists |
| Glossary | Page exists |
| Design tokens | Complete (CSS custom properties) |
| Mock data fallback | Complete (works without backend) |

**Pages:** 14 Astro pages (including /status), 25+ components, 5 React islands.

**Build:** Static HTML + JS, deployable to any host. Connects to backend via `PUBLIC_API_URL`.

### Tests — Strong coverage

| Test area | Files | Tests | Status |
|-----------|-------|-------|--------|
| Ingestion models | 1 | 14 | Passing |
| Ingestion project | 1 | 8 | Passing |
| Ingestion LLM client | 1 | 5 | Passing |
| Ingestion parse | 1 | 4 | Passing |
| Ingestion seed/load | 1 | 13 | Passing |
| Ingestion passes (all) | 1 | 13 | Passing |
| Auth (keys + expiry) | 2 | ~12 | Passing |
| Auth wiring | 1 | ~5 | Passing |
| Evidence routes | 1 | 4 | Passing |
| Review routes | 1 | 6 | Passing |
| Public endpoints | 1 | ~8 | Passing |
| Seed loader | 1 | ~12 | Passing |
| Pagination | 1 | ~5 | Passing |
| Embedding | 1 | ~5 | Passing |
| Retrieval planner | 1 | ~5 | Passing |
| Rate limiting | 1 | ~5 | Passing |
| Structured data | 1 | ~3 | Passing |
| Health (+ swagger, migration check) | 1 | 5 | Passing |
| Other (worker, logging, etc.) | 3 | ~5 | Passing |
| Integration (requires DB) | 1 | 3 | Passing (with live Postgres) |

**Total: 130 tests, 127 passing without external dependencies.**

### Documentation — Comprehensive

| Document | Location | Status |
|----------|----------|--------|
| README | `README.md` | Current |
| Vision | `VISION.md` | Current |
| Philosophy | `PHILOSOPHY.md` | Current |
| Contributing | `CONTRIBUTING.md` | Current |
| Architecture | `docs/ARCHITECTURE.md` | Current |
| Doctrine + KO model | `docs/VISION.md` | Current |
| Ingestion operator guide | `ingestion/README.md` | Current |
| Production deploy | `docs/PRODUCTION_DEPLOY.md` | Current |
| Deploy checklist | `docs/DEPLOY_CHECKLIST.md` | Current |
| Production hardening plan | `docs/superpowers/plans/2026-03-25-production-hardening.md` | Current |
| Original design docs | `docs/context/` | Preserved |
| Seed data schema | `expanded_seed/schema/` | Current |
| Implementation plan | `docs/superpowers/plans/` | Current |
| Design spec | `docs/superpowers/specs/` | Current |

## Known gaps and stub modules

### Empty modules (planned extension points)

- `src/capability_commons/audit/__init__.py` — audit trail service (no code)
- `src/capability_commons/storage/__init__.py` — file/media storage adapter (no code)
- `src/capability_commons/jobs/__init__.py` — background job scheduling (no code; outbox worker exists separately)

### Abstract adapter methods

The `GraphAdapter` and `SearchAdapter` base classes each define 4 abstract methods. All are implemented in the Postgres/relational adapters. The abstract bases exist for future Neo4j and OpenSearch adapters.

### Feature-gated functionality

- **Embedding indexing** — requires `OPENAI_API_KEY` in environment. Without it, vector columns remain NULL and search falls back to FTS-only.
- **Sentry error tracking** — requires `SENTRY_DSN` in environment. Without it, no error tracking.
- **Contradiction auto-detection** — schema and models exist, service endpoints exist, but no automated detection pipeline (contradictions must be opened manually via API).

### Integration tests

3 integration tests require a live Postgres database and fail in environments without one. These test the full object lifecycle, edge creation, and facet attachment against the real schema. They run in the CI integration job with a pgvector service container.
