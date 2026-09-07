# Capability Commons — Production Readiness TODO

> The original 38-ticket engineering backlog (Phases 0-4) is complete, and the P0/P1/stretch
> follow-up work from `updates/PLAN.md`'s gap analysis merged 2026-05-14 (see `STATUS.md`).
> No commits have landed since 2026-05-14. The items below reflect that combined state — most
> are operational/content tasks, not backend feature work.

Organized by priority tier. Items within each tier are roughly ordered by impact.

---

## Tier 0: Pick this up first

Specs for all items below live under `docs/superpowers/{specs,plans}/2026-09-06-*`. Two of the four were actually executed against the real dev database on 2026-09-06, not just spec'd — read "What actually happened" in the retrieval-verification design doc before assuming any of this is still hypothetical.

- [x] **Set up a local dev environment** — done 2026-09-06: `.venv` created (base + dev deps), and a stopped container (`capabilitycommons-db-1`, ~4 months old) with its original data volume was found and restarted on port 5435 — this is the real historical database, not a fresh reconstruction. `[ingest]` extras still not installed (disk space, see repo-hygiene checklist).
- [x] **Check whether seed objects have embeddings / are even in the database — fully done 2026-09-07.** The answer was more basic than hypothesized: **the seed pack had never been loaded into this database at all** (only the 34 GGG objects existed). Loaded it (49 objects, both `expanded_seed/` and `capability_commons_module_seed_pack_v1/`). Found and fixed two real bugs along the way: `cli/seed.py` silently dropped cross-pack edges when a second pack's `edges.csv` referenced slugs from a pack loaded in an earlier separate run; `cli/worker.py` marked outbox events processed even when the handler raised, permanently losing embeddings on any transient failure (reproduced live against the then-invalid `OPENAI_API_KEY`). Both fixed, regression test added. The API key was fixed and the worker re-run: **83 objects, 180/180 segments embedded, 0 pending outbox events** — confirmed intact after an unrelated Docker cleanup. Full account in `docs/superpowers/specs/2026-09-06-retrieval-verification-backfill-design.md`.
- [ ] **Ingest a real household-resilience source end-to-end** — still the only corpus ever run through the pipeline is the off-mission GGG newsletter. Disk space is no longer the blocker (freed 2026-09-07, see repo-hygiene checklist — 36GB free now). See `docs/superpowers/specs/2026-09-06-resilience-corpus-ingestion-design.md` (source shortlist: FEMA/USDA/OSHA public-domain guides, verified this session).
- [ ] **Fix `astro build` performance** — 10+ minutes against a live backend because the per-domain SSG cache in `src/lib/api.ts` doesn't survive Astro's per-route module instances during static generation. See `docs/superpowers/plans/2026-09-06-frontend-build-and-polish.md`.
- [x] **Re-run the eval harness — done 2026-09-07, found and fixed a third root cause.** Started the API + worker for real (fixing a stale `.env` `DATABASE_URL` still pointing at the pre-cleanup Docker port along the way). Still 3/11, but the reason had nothing to do with embeddings or intent-classifier staleness: **the entire 49-object seed pack had `lifecycle_state = 'draft'` in its own source CSVs and had never been published** — search hard-filters to `PUBLISHED` objects regardless of embedding state. Ran all 49 through the real `RegistryService.publish_version()` gate (not bypassed): 28 published and now correctly dominate top hits for on-topic queries (ranking itself works fine); 20 correctly blocked by real Pydantic schema failures (see next item). Re-running eval surfaced two further, genuinely new gaps — see the two items directly below. Full account: `docs/superpowers/specs/2026-09-06-retrieval-verification-backfill-design.md`. Latest report: `eval/reports/2026-09-07.md`.
- [x] **Author missing `structured_data` fields for 20 blocked seed objects — done 2026-09-07, eval 3/11 → 5/11.** Authored `learning_objectives` + `teach_forward` for the 11 blocked `skill_guide` objects and `budget_notes` for the 9 blocked `project_blueprint` objects, directly from each object's existing goal/steps/failure-modes content. Published via `create_version()` + `publish_version()` (not `update_draft_version()` — the seed loader sets `current_version_id` even on draft-lifecycle objects, so the in-place-edit immutability guard rejected it; a new v2 was the correct path anyway). **Found and fixed a fourth real bug along the way**: `PublishGate` requires `safety_boundary` for `project_blueprint`, but `ProjectBlueprintStructuredData` never defined that field, so it was silently stripped before the gate ever saw it — **no `project_blueprint` object could ever have published**, not just these seed instances. Fixed by adding `safety_boundary: str` to the schema (`schemas/structured_data.py`) and authoring real per-object safety content (generator CO risk, panel-work electrician requirement, asbestos/lead exposure, water-testing escalation, mutual-aid map privacy). 51/51 resilience-seed objects now published. Full account: retrieval-verification design doc's third 2026-09-07 follow-up.
- [ ] **`LocalAdaptationStructuredData` has the same missing-`safety_boundary`-field bug as `ProjectBlueprintStructuredData` had** — `COType.LOCAL_ADAPTATION` is also in `PublishGate`'s `SAFETY_BOUNDARY_REQUIRED_TYPES`, but the schema doesn't define the field. No objects of this type exist yet, so nothing is blocked by it today, but it will silently block the first one someone tries to publish. Add `safety_boundary: str` to `LocalAdaptationStructuredData` before that type is ever used for real.
- [ ] **Attach evidence-span citations to seed/curriculum content** — `/v1/public/ask` still returns `citations: []` for most resilience-domain answers even now that the objects are published, because `implementation_plan[].source_slug` names the right objects but nothing links them to an `EvidenceSpan`. Root cause: `citations` comes from `EvidenceSpan` rows explicitly linked to a version (`services/evidence.py::list_citations_for_version`), and none exist for the hand-authored curriculum content — only the ingested GGG corpus has them. For safety-adjacent content (water treatment, food safety) this is a real trust gap, not just an eval-scoring artifact, and it's the single biggest remaining lever on the eval score (5/11 as of 2026-09-07). Real ingestion (see the item above this one) naturally produces evidence-span-backed segments — likely a better lever than hand-attaching citations to synthetic curriculum text.
- [ ] **Reconcile `eval/gold/queries.yaml` against the actual seed pack** — several `expects_any` entries reference slugs that don't exist anywhere in the seed pack under any name (`water.rain-barrel`, `power.starter-solar`, `water.chlorine-treatment`). Either author that content or rewrite the gold file to match what the seed pack actually contains — don't just delete the failing assertions.

---

## Tier 1: Required for production deployment

These must be done before serving real users.

### CI/CD pipeline

- [x] **GitHub Actions workflow** — lint (ruff), type-check (mypy), test on every push/PR
- [x] **Integration test job** — spins up pgvector/pgvector:pg16 in CI, runs `test_integration.py`
- [x] **Deploy pipeline** — GitHub Actions CD: auto-deploy staging on merge to main, manual promote to production (`.github/workflows/deploy.yml`)
- [ ] **Wire the eval harness into CI** — `eval/` is cheap enough to run per-PR (per its own README) but isn't gated in `ci.yml` yet.

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
- [x] **Auth enforcement on all routes** — fixed endpoints that were missing auth checks
- [x] **Rate limit tuning** — public lowered from 300→60/min; authenticated stays at 100/min; overridable via env vars
- [ ] **Editorial auth flow** — `/review` and `/ingest` on the frontend are bearer-token surfaces with a paste-the-key login. Needs real token issuance and scope/role display before exposing to outside reviewers. Spec'd in `docs/superpowers/plans/2026-09-06-editorial-trust-tooling.md`.

### Observability

- [x] **Structured logging** — structlog with JSON output in production, colored console in dev
- [x] **Health check depth** — `/health/detailed` reports DB connectivity, Alembic migration heads, and embedding service availability
- [x] **Error tracking** — Sentry integration, opt-in via `SENTRY_DSN` env var
- [x] **Request metrics** — Prometheus metrics at `/metrics` via prometheus-fastapi-instrumentator
- [x] **Answer-quality metrics** — public `/v1/public/metrics` endpoint (citation precision, intent accuracy, action-plan coverage)

### Content safety

- [x] **Run the ingestion pipeline on a real source** — completed end-to-end against `gpt-4o` (`ingestion/projects/ggg-2026-03`). Content is off-mission (finance/geopolitics, not household resilience) — see Tier 0.
- [x] **Safety review for high-risk content** — publish gates (SAFE-001) block high-risk content without an approved review

---

## Tier 2: Should be done before public launch

### Retrieval and search

- [x] **Real hybrid retrieval** — `RetrievalService` now calls `search_hybrid()`; `PostgresSearchAdapter.search_hybrid` unions FTS + vector candidates and fuses via reciprocal rank fusion instead of only rescoring FTS hits with vector similarity
- [x] **Intent auto-detection** — `retrieval/intent.py` heuristic classifier resolves intent when the caller omits it; one edge case remains ("what is X about" → `why`)
- [x] **Structured answer synthesis** — intent-shaped composer surfaces `action_now`, contradictions, and next steps in `/v1/public/ask`, not just evidence-pack rendering
- [x] **Gold query eval set** — `eval/gold/queries.yaml` + harness (EVAL-1); needs a real resilience corpus to score meaningfully (see Tier 0) and a `--conversation` flag to exercise the multi-turn path
- [ ] **Multilingual search** — `language_code` scaffold added (MULTI-1) but not fully wired through search ranking/synthesis; the Spanish gold query still fails end-to-end
- [ ] **Query caching** — cache popular public queries by `(normalized_query, intent, context_hash)`; `RetrievalRun` rows persist but every `/v1/public/ask` call re-runs the planner

### Content population

- [ ] **First real ingestion batch on-mission** — see Tier 0
- [ ] **Second domain expansion** — run on a second domain source to validate the pipeline generalizes
- [ ] **Citation verification** — spot-check 20% of LLM-generated citations against source material for accuracy
- [ ] **Edge review** — manually review extracted edges for the first on-mission batch
- [ ] **Ingestion canonicalization** — merge/split decisions currently only move files into `_merged/`/`_split/` and log the decision; no merged or split objects are actually materialized

### Frontend integration

- [x] **Public contribution API** — `/v1/contribute/{field-report,adaptation}` (FE-CTR-1)
- [ ] **End-to-end smoke test** — run periodically; last run (2026-05-14) surfaced the build-perf and corpus issues above
- [ ] **Bundle rendering** — verify six-part bundles display correctly for objects that have them
- [ ] **Graph explorer data** — verify the D3 graph visualization renders correctly with the full graph
- [ ] **PWA update toast** — service worker registers but the UI doesn't surface a "waiting"/update-available state
- [ ] **`PUBLIC_USE_MOCK` env flag** — the frontend's mock-data fallback in `src/lib/api.ts` is currently unconditional; gate it so production builds against an unhealthy backend fail loudly instead of silently serving stale mock data

### API documentation

- [x] **Enable Swagger UI** — `/docs` and `/redoc` enabled on the FastAPI app
- [ ] **Schema documentation** — auto-generate or write a reference for all request/response models
- [ ] **Public API guide** — document the public endpoints (`/v1/public/*`) for third-party consumers

### Testing gaps

- [x] **Evidence routes** / **Review routes** — auth enforcement tests
- [ ] **Retrieval service** — add integration test that exercises the full plan → execute → assemble pipeline
- [ ] **Publication service** — add tests for bundle rendering and learning path assembly
- [ ] **Search adapter** — add tests for `fetch_segments()` method
- [ ] **Intent classifier** — add a test for the "what is X about" → `why` gap identified in the 2026-05-14 smoke run

---

## Tier 3: Should be done for operational maturity

### Audit and governance

- [x] **Implement audit service** — append-only `AuditEvent` log, API routes at `/v1/audit/objects/{id}` and `/v1/audit/timeline`
- [ ] **Contradiction detection pipeline** — currently contradictions must be opened manually
- [x] **Review dashboard backend** — `GET /v1/reviews/queue` now filterable by `lifecycle_state` and `risk_band` (REV-2); frontend integration still pending
- [ ] **Citation QA dashboard** — per-object reviewer view to spot-check citation strength; currently only surfaced in aggregate via `/v1/public/metrics`. Spec'd in `docs/superpowers/plans/2026-09-06-editorial-trust-tooling.md`.

### Storage and media

- [x] **Implement storage adapter** — `StorageAdapter` ABC with `LocalStorageAdapter` and `S3StorageAdapter` stub
- [x] **Object file management** — CRUD routes for upload/list/download/delete with SHA-256 checksums

### Background jobs

- [x] **Implement job scheduler** — DB-backed `IngestService` tracks ingest jobs and per-pass status, now mirrored live into `IngestJob`/`IngestJobPass`; general background job runner still a stub for non-ingest work
- [ ] **Embedding backfill job** — for existing objects created before embeddings were enabled

### Scaling extension points

- [ ] **Neo4j adapter** — implement `GraphAdapter` for Neo4j when graph query complexity exceeds SQL BFS (likely at 10,000+ nodes)
- [ ] **OpenSearch adapter** — implement `SearchAdapter` for OpenSearch when FTS volume/faceting requires it
- [ ] **Read replicas** — configure async read sessions against a Postgres replica for search-heavy workloads

### Offline and distribution

- [ ] **Offline export** — generate static bundles (PDF, EPUB) for the core corpus
- [ ] **Low-bandwidth mirror** — static HTML export of all published objects
- [ ] **Print-ready field guides** — generate formatted print layouts from bundles

### Community infrastructure

- [ ] **Contributor attribution** — track who contributed what; display on the site
- [ ] **Local adaptation workflow** — process for submitting region-specific variants (the new `/v1/contribute/adaptation` endpoint is the backend half of this)
- [ ] **Field testing protocol** — how field test results attach to objects and influence lifecycle state (the new `/v1/contribute/field-report` endpoint is the backend half of this)
- [ ] **Translation workflow** — translated object versions with `TRANSLATED_FROM` edge type

### Repo/process housekeeping

Checklist form: `docs/superpowers/plans/2026-09-06-repo-hygiene-checklist.md`.

- [ ] **Delete stale `feat/ingestion-tooling` branch** — local and `origin`; it's a pre-merge pointer with 0 commits ahead of `main`
- [ ] **Document `gh auth login` as a prerequisite in `CONTRIBUTING.md`** — a missing-auth error was hit and worked around during the last PR stack, but never documented
- [ ] **Set up a cleaner stacked-PR workflow** — merging the base PR of a stack first orphans and auto-closes the stretch PR (had to be recreated against `main`); consider graphite, spr-cli, or squash-merging the stretch branch directly
- [ ] **Clean up ingest working directories** — `_pre_envelope/_merged/_split`/`_holdback` subpaths from the GGG run are committed to the repo; decide on a retention policy and likely `.gitignore` them going forward
- [ ] **Resolve `_holdback/finance.portfolio-holdings-table.yaml`** — held back from publish (fewer than 2 citations); either re-cite and publish, or delete with intent

---

## Tier 4: Future enhancements

### Curriculum and learning

- [ ] **Adaptive learning paths** — personalized paths based on learner context (climate, housing type, budget, existing skills)
- [ ] **Assessment engine** — implement the assessment model beyond current schema support
- [ ] **Progress tracking** — mark objects as completed, track progress through learning paths
- [ ] **Cohort support** — group learners into cohorts with shared field reports

### AI capabilities

- [ ] **Personalized retrieval** — use learner profile (context facets) to customize retrieval results
- [ ] **Conversational tutor improvements** — persistent conversation history, follow-up questions, suggested next steps
- [ ] **Automated content quality scoring** — LLM assessment of draft objects against the doctrine checklist
- [ ] **Cross-source contradiction detection** — automatically flag claims conflicting with existing published objects during ingestion

### Platform

- [ ] **Multi-workspace support** — schema supports it; seeding and public API still assume a single workspace
- [ ] **Webhook/event API** — expose outbox events as webhooks for external integrations
- [ ] **GraphQL layer** — alternative to REST for flexible graph queries
- [ ] **API versioning** — plan the v2 strategy before breaking changes accumulate

---

## Quick reference: what to do first

If you're picking up this project:

1. ~~Set up CI (GitHub Actions with pytest + Docker)~~ Done
2. ~~Enable auth, configure HTTPS, set up backups~~ Done
3. ~~Set up CD pipeline (staging auto-deploy, manual production)~~ Done
4. ~~Close PLAN.md P0/P1 correctness gaps in ingestion and retrieval~~ Done (2026-05-14)
5. Set up a local dev environment (no `.venv` in this checkout) and re-run the test suite and eval harness to confirm the 2026-05-14 state still holds
6. Ingest a real household-resilience source end-to-end (see Tier 0) — this is the actual blocker on the vision, not backend feature work
7. Fix the `astro build` static-generation performance issue before attempting a real production frontend build
8. Review the output, fix issues, load to database
9. Deploy with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
10. Verify the frontend connects and renders correctly
11. Ship it
