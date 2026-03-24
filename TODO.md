# Capability Commons — Production Readiness TODO

Organized by priority tier. Items within each tier are roughly ordered by impact.

---

## Tier 1: Required for production deployment

These must be done before serving real users.

### CI/CD pipeline

- [ ] **GitHub Actions workflow** — lint, type-check, test on every push/PR
  - Run `pytest tests/ --ignore=tests/test_integration.py` (unit tests, no DB required)
  - Run `ruff check` or `flake8` for linting
  - Run `mypy` for type checking (currently not configured)
  - Build Docker image to verify Dockerfile isn't broken
- [ ] **Integration test job** — spin up Postgres via `docker-compose` in CI, run `test_integration.py`
- [ ] **Deploy pipeline** — automated deploy to staging on merge to main, manual promote to production

### Environment and secrets

- [ ] **Secret management** — move `OPENAI_API_KEY`, `DATABASE_URL`, and API key seeds out of `.env` into a secrets manager (Vault, AWS SSM, or platform-native)
- [ ] **Separate staging and production configs** — distinct database URLs, CORS origins, rate limits
- [ ] **HTTPS enforcement** — ensure API is served behind TLS (reverse proxy config for nginx/Caddy)

### Database operations

- [ ] **Connection pooling** — configure `pool_size`, `max_overflow`, `pool_recycle` in SQLAlchemy engine for production load
- [ ] **Backup strategy** — automated `pg_dump` on schedule, tested restore procedure
- [ ] **Migration safety** — add a pre-deploy check that pending migrations are applied before the app starts (or fail loudly)

### Authentication and authorization

- [ ] **Auth enabled by default in production** — currently `AUTH_ENABLED=false` is the default; flip for prod
- [ ] **API key rotation** — add `expire_at` support and key rotation CLI command
- [ ] **Rate limit tuning** — review `RATE_LIMIT_PER_MINUTE=100` and `RATE_LIMIT_PUBLIC_PER_MINUTE=300` against expected traffic

### Observability

- [ ] **Structured logging** — switch from print/basic logging to structured JSON logs (for log aggregation)
- [ ] **Health check depth** — `/health/detailed` should check not just DB connectivity but migration version, disk space, embedding service availability
- [ ] **Error tracking** — integrate Sentry or equivalent for unhandled exception reporting
- [ ] **Request metrics** — add Prometheus metrics or equivalent (request count, latency percentiles, error rates)

### Content safety

- [ ] **Run the ingestion pipeline on a real source** — the pipeline is implemented but has not yet produced a full content batch from a real PDF. At least one end-to-end run (parse through load) must be completed and the output reviewed before going live.
- [ ] **Safety review for high-risk content** — any objects with `risk_band: high` or `expert_only` need manual safety review before `PUBLISHED` state

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

- [ ] **End-to-end smoke test** — verify the site can fetch and render all object types from the live backend (concept_note, skill_guide, project_blueprint, module, assessment)
- [ ] **Bundle rendering** — verify six-part bundles display correctly for objects that have them
- [ ] **Graph explorer data** — verify the D3 graph visualization renders correctly with the full 49-object + 175-edge graph
- [ ] **Search integration** — verify SearchPanel connects to backend and returns useful results
- [ ] **AI tutor** — verify AskTutor connects to the retrieval API and returns grounded answers with citations

### API documentation

- [ ] **Enable Swagger UI** — FastAPI auto-generates OpenAPI docs; enable the `/docs` endpoint in production (or at least staging)
- [ ] **Schema documentation** — auto-generate or write a reference for all request/response models
- [ ] **Public API guide** — document the public endpoints (`/v1/public/*`) for third-party consumers

### Testing gaps

- [ ] **Evidence routes** — add tests for evidence source/span creation and edge citation attachment
- [ ] **Review routes** — add tests for review submission, contradiction opening, and resolution
- [ ] **Retrieval service** — add integration test that exercises the full plan → execute → assemble pipeline
- [ ] **Publication service** — add tests for bundle rendering and learning path assembly
- [ ] **Search adapter** — add tests for `fetch_segments()` method

---

## Tier 3: Should be done for operational maturity

These make the platform maintainable and extensible over time.

### Audit and governance

- [ ] **Implement audit service** — the `audit/` module is a stub. Implement event logging for object creates, edits, publishes, and edge changes. Critical for the governance model (transparent version history).
- [ ] **Contradiction detection pipeline** — currently contradictions must be opened manually. Add automated detection (e.g., when two objects in the same domain make conflicting claims, flag for review).
- [ ] **Review dashboard** — expose review queue through the API and frontend (objects in `IN_REVIEW` state, pending safety reviews, open contradictions)

### Storage and media

- [ ] **Implement storage adapter** — the `storage/` module is a stub. Define the interface for file/media uploads (diagrams, photos, worksheets). Implement for local filesystem first, then S3-compatible.
- [ ] **Object file management** — the `object_files` table exists but no API routes serve file uploads/downloads

### Background jobs

- [ ] **Implement job scheduler** — the `jobs/` module is a stub. The outbox worker handles publish events, but other background work (batch embedding, scheduled validation, stale content detection) needs a proper job runner.
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

1. Set up CI (GitHub Actions with pytest + Docker)
2. Run the ingestion pipeline on one real source document end-to-end
3. Review the output, fix issues, load to database
4. Enable auth, configure HTTPS, set up backups
5. Deploy with Docker Compose behind a reverse proxy
6. Verify the frontend connects and renders correctly
7. Enable Swagger UI for API documentation
8. Ship it
