# Capability Commons — Production Readiness TODO

> **All 38 engineering backlog tickets are complete** (Phases 0-4). The items below are operational tasks for production deployment — not feature work.

Organized by priority tier. Items within each tier are roughly ordered by impact.

---

## Tier 1: Required for production deployment

These must be done before serving real users.

### CI/CD pipeline

- [x] **GitHub Actions workflow** — lint (ruff), type-check (mypy), test on every push/PR
  - Runs `pytest tests/ --ignore=tests/test_integration.py` (unit tests, no DB required)
  - Runs `ruff check` and `ruff format --check` for linting
  - Runs `mypy` for type checking
  - Builds Docker image to verify Dockerfile isn't broken
- [x] **Integration test job** — spins up pgvector/pgvector:pg16 in CI, runs `test_integration.py`
- [x] **Deploy pipeline** — GitHub Actions CD: auto-deploy staging on merge to main, manual promote to production (`.github/workflows/deploy.yml`)

### Environment and secrets

- [ ] **Secret management** — move `OPENAI_API_KEY`, `DATABASE_URL`, and API key seeds out of `.env` into a secrets manager (Vault, AWS SSM, or platform-native)
- [x] **Separate staging and production configs** — `.env.staging` and `.env.production` templates with environment-appropriate defaults
- [x] **HTTPS enforcement** — Caddy reverse proxy in `docker-compose.prod.yml` with auto-TLS via Let's Encrypt

### Database operations

- [x] **Connection pooling** — configurable `pool_size`, `max_overflow`, `pool_recycle`, `pool_pre_ping` via env vars
- [x] **Backup strategy** — automated daily pg_dump in Docker (14-day retention) + manual `deploy/backup.sh` and `deploy/restore.sh`
- [x] **Migration safety** — startup check warns if pending Alembic migrations exist

### Authentication and authorization

- [x] **Auth enabled by default in production** — `AUTH_ENABLED=true` is the default in config
- [x] **API key rotation** — `expire_at` column, `is_key_expired` check, `rotate` CLI command with `--ttl-hours`
- [x] **Auth enforcement on all routes** — fixed 7 endpoints (evidence spans, edge citations, citations list, contradiction resolve, verify, dispute, deprecate) that were missing auth checks
- [x] **Rate limit tuning** — public lowered from 300→60/min; authenticated stays at 100/min; overridable via env vars

### Observability

- [x] **Structured logging** — structlog with JSON output in production, colored console in dev
- [x] **Health check depth** — `/health/detailed` reports DB connectivity, Alembic migration heads, and embedding service availability
- [x] **Error tracking** — Sentry integration, opt-in via `SENTRY_DSN` env var
- [x] **Request metrics** — Prometheus metrics at `/metrics` via prometheus-fastapi-instrumentator (opt-out via `METRICS_ENABLED=false`)

### Content safety

- [ ] **Run the ingestion pipeline on a real source** — the pipeline is implemented but has not yet produced a full content batch from a real PDF. At least one end-to-end run (parse through load) must be completed and the output reviewed before going live.
- [x] **Safety review for high-risk content** — publish gates (SAFE-001) block high-risk content without an approved review; safety boundary required for actionable types

---

## Tier 2: Should be done before public launch

These are important for a good user experience and operational confidence.

### Embedding and search

- [ ] **Embedding indexing on publish** — the outbox worker handles `version.published` events but the embedding indexing pipeline should be verified end-to-end (publish object → outbox event → worker picks up → segments created → embeddings computed → indexed)
- [ ] **Search relevance tuning** — test hybrid search (FTS + embedding) with real queries against the seeded corpus; adjust weight balance if needed
- [ ] **Search result quality** — add facet filtering to search (by domain, stage, difficulty, risk_band) if not already wired

### Content population

- [ ] **First real ingestion batch** — run the pipeline on one reference book (e.g., the permaculture reference material in `ingestion/`), review output, load to database
- [ ] **Second domain expansion** — run on a second domain source to validate the pipeline generalizes
- [ ] **Citation verification** — spot-check 20% of LLM-generated citations against source material for accuracy
- [ ] **Edge review** — manually review extracted edges for the first batch; LLM-generated edges need human validation

### Frontend integration

- [x] **Frontend submodule** — integrated at `apps/site` as git submodule (FE-001)
- [x] **Guided ask** — AskTutor rewritten for POST /v1/public/ask with structured responses (FE-002)
- [x] **Server-side search** — SearchPanel rewritten for POST /v1/search with UX filters (FE-003)
- [x] **Implementation profiles** — StructuredPayload renders implementation details (FE-004)
- [x] **Print styles** — print.css extended for all new sections (FE-005)
- [x] **User feedback** — backend POST /v1/feedback + frontend AnswerFeedback component (FE-006)
- [ ] **End-to-end smoke test** — verify the site can fetch and render all object types from the live backend
- [ ] **Bundle rendering** — verify six-part bundles display correctly for objects that have them
- [ ] **Graph explorer data** — verify the D3 graph visualization renders correctly with the full graph

### API documentation

- [x] **Enable Swagger UI** — `/docs` and `/redoc` enabled on the FastAPI app
- [ ] **Schema documentation** — auto-generate or write a reference for all request/response models
- [ ] **Public API guide** — document the public endpoints (`/v1/public/*`) for third-party consumers

### Testing gaps

- [x] **Evidence routes** — auth enforcement tests for all evidence endpoints (4 tests)
- [x] **Review routes** — auth enforcement tests for all review endpoints (6 tests)
- [ ] **Retrieval service** — add integration test that exercises the full plan → execute → assemble pipeline
- [ ] **Publication service** — add tests for bundle rendering and learning path assembly
- [ ] **Search adapter** — add tests for `fetch_segments()` method

---

## Tier 3: Should be done for operational maturity

These make the platform maintainable and extensible over time.

### Audit and governance

- [ ] **Implement audit service** — the `audit/` module is a stub. Implement event logging for object creates, edits, publishes, and edge changes. Critical for the governance model (transparent version history).
- [ ] **Contradiction detection pipeline** — currently contradictions must be opened manually. Add automated detection (e.g., when two objects in the same domain make conflicting claims, flag for review).
- [x] **Review dashboard** — `GET /v1/reviews/queue` exposes objects in `IN_REVIEW` state (ING-007); frontend integration pending

### Storage and media

- [ ] **Implement storage adapter** — the `storage/` module is a stub. Define the interface for file/media uploads (diagrams, photos, worksheets). Implement for local filesystem first, then S3-compatible.
- [ ] **Object file management** — the `object_files` table exists but no API routes serve file uploads/downloads

### Background jobs

- [x] **Implement job scheduler** — DB-backed `IngestService` tracks ingest jobs and per-pass status (ING-007); general background job runner still a stub for non-ingest work
- [ ] **Embedding backfill job** — for existing objects that were created before embeddings were enabled, run a batch job to compute and index embeddings

### Scaling extension points

- [ ] **Neo4j adapter** — implement `GraphAdapter` for Neo4j when graph query complexity exceeds what SQL BFS can handle efficiently (likely at 10,000+ nodes)
- [ ] **OpenSearch adapter** — implement `SearchAdapter` for OpenSearch when full-text search volume or faceting complexity requires it
- [ ] **Read replicas** — configure async read sessions against a Postgres replica for search-heavy workloads

### Offline and distribution

- [ ] **Offline export** — generate static bundles (PDF, EPUB) for the core corpus, downloadable from the site
- [ ] **Low-bandwidth mirror** — static HTML export of all published objects for deployment on low-bandwidth servers
- [ ] **Print-ready field guides** — generate formatted print layouts from bundles (hook + primer + guide + reference per topic)

### Community infrastructure

- [ ] **Contributor attribution** — track who contributed what in object provenance metadata; display on the site
- [ ] **Local adaptation workflow** — define the process for submitting region-specific variants of existing objects
- [ ] **Field testing protocol** — define how field test results get attached to objects and influence lifecycle state progression
- [ ] **Translation workflow** — support for translated versions of objects with `TRANSLATED_FROM` edge type

---

## Tier 4: Future enhancements

These extend the platform's reach and capability.

### Curriculum and learning

- [ ] **Adaptive learning paths** — generate personalized paths based on learner context (climate, housing type, budget, existing skills)
- [ ] **Assessment engine** — implement the assessment model (artifact exists, performance demonstrated, oral explanation, teach-forward) beyond the current schema support
- [ ] **Progress tracking** — allow users to mark objects as completed and track progress through learning paths
- [ ] **Cohort support** — group learners into cohorts working through the same path, with shared field reports

### AI capabilities

- [ ] **Personalized retrieval** — use learner profile (context facets) to customize retrieval results
- [ ] **Conversational tutor improvements** — maintain conversation history, support follow-up questions, suggest next steps based on what was discussed
- [ ] **Automated content quality scoring** — use LLM to assess draft objects against the doctrine checklist (plain language, action-terminated, locally adapted, etc.)
- [ ] **Cross-source contradiction detection** — when ingesting new sources, automatically flag claims that conflict with existing published objects

### Platform

- [ ] **Multi-workspace support** — the schema supports multiple workspaces but the seeding and public API assume a single workspace; generalize for organizational forks
- [ ] **Webhook/event API** — expose outbox events as webhooks for external integrations
- [ ] **GraphQL layer** — add GraphQL endpoint for flexible graph queries (alternative to REST)
- [ ] **API versioning** — currently all routes are under `/v1`; plan the v2 strategy before breaking changes accumulate

---

## Quick reference: what to do first

If you're picking up this project and want to get to production:

1. ~~Set up CI (GitHub Actions with pytest + Docker)~~ Done
2. ~~Enable auth, configure HTTPS, set up backups~~ Done
3. ~~Set up CD pipeline (staging auto-deploy, manual production)~~ Done
4. Run the ingestion pipeline on one real source document end-to-end
5. Review the output, fix issues, load to database
6. Deploy with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
7. Verify the frontend connects and renders correctly
8. Ship it
