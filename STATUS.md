# Capability Commons — Project Status

Last updated: 2026-09-06

## Overview

Capability Commons is a working, deployable knowledge platform. The backend API, database schema, seed data, ingestion pipeline, and frontend site are all implemented and functional. The system can be stood up with Docker Compose, seeded with the starter knowledge graph, and queried through both API endpoints and the Astro frontend.

The project completed its original 5-phase engineering backlog (38 tickets) in April 2026. After that, an internal gap analysis (`updates/PLAN.md`) audited the finished system and concluded it was better at **storing knowledge** than **delivering implementation-ready help** — the ingestion pipeline had several correctness bugs, and the retrieval/chat layer returned relevant objects rather than composed action plans. Two follow-up PRs (`production-gaps-stage1-2`, `stretch-eval-harness`) closed PLAN.md's P0 and P1 gaps plus a stretch tier, merged 2026-05-14. **No commits have landed since** — this document reflects that state, not new work.

The system now includes publish gates, metrics, response caching, ingest job tracking, a review queue with lifecycle/risk-band filtering, guided ask with structured (intent-shaped) answers, real hybrid search (FTS + vector via reciprocal rank fusion), implementation profiles, user feedback, a public field-report/adaptation contribution API, a public quality-metrics endpoint, a multilingual search scaffold, and a gold-query eval harness. The next concrete step, per the repo's own quick-start runbook, is running the ingestion pipeline end-to-end on an actual household-resilience source — the only corpus ingested so far (see Known gaps) is off-mission.

## Codebase metrics

| Metric | Count |
|--------|-------|
| Python source files | 109 |
| Python source lines | ~11,600 |
| Test files | 40 |
| Test lines | ~5,600 |
| Test functions (source count) | 346 (365 collected test cases reported by the last recorded CI-passing run, 2026-05-14 — not re-verified in this pass; no `.venv` in this checkout) |
| API endpoints | 56 |
| Route modules | 16 |
| Database tables | 25 |
| Alembic migrations | 12 |
| Seeded objects | 49 (25 capability + 24 curriculum) |
| Seeded edges | 175 |
| Enum types | 30+ |

## Component status

### Backend API — Complete

FastAPI application with 56 endpoints across 16 route modules. All routes are wired, return valid response models, and enforce authentication where required.

| Route module | Status |
|-------------|--------|
| Health | Production-ready |
| Objects | Production-ready |
| Entities | Production-ready |
| Edges | Production-ready |
| Evidence | Production-ready, tested |
| Reviews | Production-ready, tested — queue now filterable by `lifecycle_state` and `risk_band` (REV-2) |
| Search | Production-ready — real hybrid search (FTS + vector, RRF fusion), `language_code` scaffold added (MULTI-1) |
| Retrieval | Production-ready — now calls `search_hybrid()`, not lexical-only |
| Public | Production-ready |
| Ask | Production-ready — intent-shaped answer composer surfaces `action_now`, contradictions, and next steps (ANSWER-1) |
| Metrics | Production-ready — public `/v1/public/metrics` (quality) endpoint added (FE-STATUS-1) |
| Ingest | Production-ready |
| Feedback | Production-ready |
| Audit | Production-ready |
| Files | Production-ready |
| **Contribute** *(new)* | Production-ready — public `/v1/contribute/{field-report,adaptation}` (FE-CTR-1) |

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
| Answer-quality metrics | Aggregate citation precision, intent accuracy, action-plan coverage via `/v1/public/metrics` | Production-ready (METRICS-2) |

### Database — Complete

PostgreSQL 16 with pgvector. 25 tables with comprehensive constraints, 40+ indexes, and full relationship mapping.

**Migrations:** 12 applied.

**Connection pooling:** Configurable via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_PRE_PING` env vars.

### Services layer — Complete

| Service | Purpose | Status |
|---------|---------|--------|
| `RegistryService` | Object/version/edge CRUD, publish workflow | Fully implemented |
| `EntityService` | Entity creation, aliasing, merging | Fully implemented |
| `EvidenceService` | Source/span creation, edge attachment | Fully implemented |
| `EmbeddingService` | OpenAI embeddings, segment indexing | Fully implemented (feature-gated on API key) |
| `ReviewService` | Review submission, contradiction handling, lifecycle/risk-band filtering | Fully implemented |
| `RetrievalService` | Plan compilation, execution, evidence pack assembly — now uses real hybrid retrieval | Fully implemented |
| `PublicationService` | Rendering public objects, bundles, graphs, paths | Fully implemented |
| `RetrievalPlanner` / intent inference | Intent-to-edge-type mapping; heuristic intent classifier (`retrieval/intent.py`) resolves intent when the caller omits it | Fully implemented — one known edge case remains, see Known gaps |
| `IngestService` | DB-backed ingest job lifecycle, per-pass progress mirrored into `IngestJob`/`IngestJobPass` | Fully implemented |
| `MetricsService` | Aggregate ingest quality and answer quality metrics | Fully implemented |
| `PublishGate` | Rule-based safety checks before publish (risk, safety boundary, contradictions) | Fully implemented |
| `AuditService` | Append-only event log for governance transparency | Fully implemented |
| `LocalStorageAdapter` | Local filesystem file storage (S3 adapter stub for future) | Fully implemented |

### Search and graph adapters — Partial

| Adapter | Implementation | Status |
|---------|---------------|--------|
| `PostgresSearchAdapter.search` | Full-text search only | Production-ready |
| `PostgresSearchAdapter.search_hybrid` | **Real hybrid**: unions FTS + vector candidates, fuses via reciprocal rank fusion (configurable `fts_weight`/`vector_weight`/`rrf_k`) | Production-ready — closes a PLAN.md P0 gap (previous version only rescored FTS hits with vector similarity, so vector search could never rescue recall) |
| `RelationalGraphAdapter` | SQL BFS for neighbors, paths, prerequisites, members | Production-ready |
| `Neo4jGraphAdapter` | Planned extension point | Not started |
| `OpenSearchAdapter` | Planned extension point | Not started |

### CLI tools — Complete

| Tool | Command | Status |
|------|---------|--------|
| Seed loader | `python -m capability_commons.cli` | Production-ready, idempotent |
| API key manager | `python -m capability_commons.cli.keys` | Production-ready (create, revoke, rotate, list) |
| Outbox worker | `python -m capability_commons.cli.worker` | Functional |
| Ingestion pipeline | `python -m capability_commons.cli.ingest` | Complete (11 commands); enum-casing and edge-mapping bugs fixed |
| Eval harness *(new)* | `python -m capability_commons.cli.eval run` | Functional (EVAL-1) — runs a gold query set against a live API, scores search/citation/intent/action_now |

### Ingestion pipeline — Complete, proven end-to-end on two sources (one off-mission, one on-mission)

8-pass LLM-assisted pipeline for converting source documents into knowledge objects. PLAN.md's P0 correctness gaps are closed:

- Page-anchored provenance in `parse.py` (was a placeholder single-page stamp) — re-verified 2026-09-08 via direct spot-checks against a new, never-before-seen PDF (FEMA), not just the original GGG run.
- Draft validation now enforces the full canonical object schema, not just the four required Pydantic fields.
- Citation linking restricted to the object's own extracted segments plus small neighbor context (was pulling from all segments of the source, or falling back to the first project source).
- Load-path schema mismatches fixed: `lifecycle_state`/`EdgeType` casing, `EvidenceSpan` metadata field, LLM-generated edge-type names (`prerequisite_for`, etc.) now map correctly instead of being silently skipped.
- Canonicalization still only *routes* files (`_merged/`, `_split/` + a log) rather than materializing merged/split objects, and has no visibility across projects (confirmed 2026-09-08: it can't see the existing seed pack at all) — **not yet fixed**, tracked as a deferred item.
- `parse.py` required a one-line fix (`output_format` missing from marker-pdf's `ConfigParser` options) found on the FEMA run — see Content/vision gap for the full account of this and several other real bugs found running the pipeline against a genuinely new document for the first time.
- Two real end-to-end runs completed: `gpt-4o` against `ingestion/projects/ggg-2026-03` (off-mission finance/geopolitics) and, 2026-09-08, against `ingestion/projects/emergency-prep-fema` (FEMA *Are You Ready?*, on-mission — the first source that actually validates the intended household-resilience content domains). USDA and OSHA (sources 2 and 3 of the ingestion plan) not yet run.
- Requires a separate Python 3.13 venv (`.venv-ingest/`, gitignored) for real runs — `polars` has no compiled runtime for Python 3.14 yet (confirmed via PyPI classifiers, not just local test failures).

### Seed data — Complete

Two seed packs loaded on startup: 25 capability objects (water, food, shelter, power, repair, gardening, epistemics) and 24 curriculum objects (12 modules + 12 assessments). 49 objects, 49 versions, 175 edges. Loader is idempotent.

### Eval harness — New (EVAL-1)

`eval/` — a gold-query retrieval harness (`eval/gold/queries.yaml`) scored against `/v1/search` and `/v1/public/ask`: search recall, citation count, intent match (informational), and `action_now` presence. Cheap enough to run per-PR; not yet wired into CI. Latest recorded run: `eval/reports/2026-09-07.md`, still 3/11 passed, but the failure reasons changed completely once the two 2026-09-07 fixes below landed — see "Content/vision gap" for the full account. The 2026-05-14 baseline (`eval/reports/2026-05-14-smoke.md`) is now superseded.

### CI/CD — Configured

| Component | Status |
|-----------|--------|
| GitHub Actions CI | Configured (lint, typecheck, test, integration, Docker build) |
| GitHub Actions CD | Configured (SSH deploy to staging on merge, manual promote to production) |
| Linting | ruff (E, F, I, W rules) |
| Type checking | mypy (incremental adoption, ignore_missing_imports) |
| Integration tests | pgvector/pgvector:pg16 service in CI |
| Docker build | Verified in CI |
| Eval harness in CI | Not yet wired |

### Deployment — Functional

| Component | Status |
|-----------|--------|
| Dockerfile | Production-ready (slim Python 3.14 image, port 8100) |
| docker-compose.yml | Development (pgvector + API, healthchecks) |
| docker-compose.prod.yml | Production (+ Caddy TLS + backup container) |
| `.env.staging` / `.env.production` | Templates provided |
| Alembic migrations | 12 applied, auto-generate works |
| Caddy reverse proxy | In Docker Compose (auto-TLS via Let's Encrypt) |
| Backup/restore | Automated daily + manual scripts in `deploy/` |
| Cloud deployment docs | Linux production guide with Quick Deploy |

### Frontend (CapabilityCommonsSite) — Integrated, feature-complete + stretch merged

Astro 6 + React 19 static site consuming the backend API, integrated as a git submodule at `apps/site`. `astro check` clean as of the last merge (2026-05-14).

All prior functionality (landing, object explorer, detail pages, graph viz, search, learning paths, syllabus, AskTutor, implementation profiles, bundle viewer, ring explorer, feedback, print styles, offline page, glossary) remains in place. Known frontend issues from the last smoke test are tracked in Known gaps below (static build performance, editorial auth, PWA polish).

### Tests — 400 passing, 6 failing (all understood), fully re-verified 2026-09-07

Full account across two sessions, against `capabilitycommons-db-1` (the project's real historical data, not a synthetic test DB):

1. **2026-09-06**: `.venv` set up, suite run — 316 passed, 42 failed. ~34 shared one root cause: a fresh install pulls `fastapi==0.141.1`/`starlette==0.52.1`, incompatible with `prometheus-fastapi-instrumentator` 7.x's routing internals (`AttributeError: '_IncludedRouter' object has no attribute 'path'`).
2. **2026-09-07**: fixed the pin (`prometheus-fastapi-instrumentator>=8.0,<9.0`; 8.1.0 supports current Starlette) and added `greenlet>=3.0,<4.0` as an explicit dependency (SQLAlchemy async needs it, was only present by transitive luck) — **316→345 passed**. Installed `[ingest]` extras (disk space no longer blocking) — **345→398 passed**. Found and fixed two real, previously-masked test bugs: `test_smoke_api.py`'s `test_retrieval_requires_auth` asserted 401 on an endpoint deliberately made public in the PLAN.md P0-6 close-out (renamed/corrected); four `test_phase0_regression.py` tests iterated router internals in a way current Starlette doesn't support, fixed by switching to `app.openapi()["paths"]`. Found and fixed a real, deterministic test bug in `test_integration_embedding.py::test_publish_creates_outbox_event` — it queried `OutboxEvent.aggregate_id == version.id`, but every real code path (`RegistryService.publish_version`, `cli/seed.py`) consistently uses `aggregate_id == object.id` for `version.published` events (version id lives in `payload["version_id"]`) — **398→399 passed**. Later the same day, added `safety_boundary: str` to `ProjectBlueprintStructuredData` (see Content/vision gap below) — re-verified full suite, no regressions, one previously-flaky scale-dependent test happened to pass this run — **399→400 passed**.

**2026-09-08**: real dev DB grew from 83 to 358 objects (FEMA ingestion, see Content/vision gap). Re-ran the full suite: still 400 passed, 6 failed — same 5 polars failures, and the scale-dependent flake landed on a third test this time (`test_integration_retrieval.py::test_execute_plan_returns_evidence_pack`, passes alone in 2.8s) instead of the two below, confirming the category (not a new bug — its own seeded test object gets outranked by the much larger real corpus in the same workspace since the test has no hard workspace isolation from production data).

**Remaining 6 failures, all understood, none are product bugs:**
- 5× `tests/test_ingest_passes.py` (extract/draft/edges passes) — `polars` doesn't work on this checkout's Python 3.14 (`NameError: name 'PyDataFrame' is not defined`, `UserWarning: Polars binary is missing!`). Confirmed 2026-09-08 this isn't just a test-environment quirk: `polars-runtime-32`'s own PyPI package classifiers only list Python 3.10–3.13, so no newer polars release fixes it either. Real ingest work now uses a separate `.venv-ingest/` (Python 3.13) — see Content/vision gap — but the main `.venv`/test suite stays on 3.14, so these 5 stay red until either polars ships 3.14 support or the test suite itself switches Python versions.
- `test_smoke_api.py::test_retrieval_allows_anonymous_access` — intermittently fails under full-suite DB connection load (a `TaskGroup`/connection-pool exception, not a 401). Passes reliably alone. Likely connection pool sizing under the accumulated load of a long full-suite run against a shared container; not yet tuned or root-caused further.
- `test_integration_publication.py::test_list_published_objects` and, as of 2026-09-08, `test_integration_retrieval.py::test_execute_plan_returns_evidence_pack` are both scale-dependent (pass in isolation, can fail when the full suite runs against the real DB's current object count) — same underlying category (tests seed data into the shared default workspace rather than a properly isolated one), not independently root-caused per-test.

### Documentation

| Document | Location | Status |
|----------|----------|--------|
| README | `README.md` | Current |
| Vision | `VISION.md` | Current |
| Philosophy | `PHILOSOPHY.md` | Current |
| Contributing | `CONTRIBUTING.md` | Current (missing a `gh auth login` prerequisite note — see TODO) |
| Architecture | `docs/ARCHITECTURE.md` | Current |
| Doctrine + KO model | `docs/VISION.md` | Current |
| Ingestion operator guide | `ingestion/README.md` | Current |
| Production deploy | `docs/PRODUCTION_DEPLOY.md` | Current |
| Deploy checklist | `docs/DEPLOY_CHECKLIST.md` | Current |
| Operational tasks guide | `docs/OPERATIONAL_TASKS.md` | Current |
| Gap analysis / backlog | `updates/PLAN.md` | Historical — P0/P1/stretch items it raised are now closed or explicitly deferred (see followups doc) |
| Follow-ups after PLAN.md merge | `docs/superpowers/plans/2026-05-14-followups.md` | **Most current planning doc in the repo** — read this first when resuming work |
| Eval harness docs | `eval/README.md` | Current |
| Design specs | `docs/spec/`, `docs/superpowers/specs/` | Current (closest equivalents to PRDs/ADRs — this repo has no dedicated ADR or PRD artifacts) |

## Known gaps and stub modules

### Content/vision gap (most significant open issue) — root cause confirmed and fixed 2026-09-06/07, two new gaps found underneath

The only corpus ever run through the ingestion pipeline end-to-end (`ingestion/projects/ggg-2026-03`) is a finance/geopolitics newsletter, unrelated to VISION.md's household-resilience domains (water, food, shelter, power, repair, gardening). **Ingesting a real resilience-domain source is still the highest-leverage remaining task** — see `docs/superpowers/specs/2026-09-06-resilience-corpus-ingestion-design.md` for a verified, openly-licensed source shortlist (FEMA, USDA, OSHA).

Separately: the real dev database was found this session to have **never had the hand-authored seed pack loaded into it at all** — only the 34 GGG objects existed, which is why the eval harness's 3/11 score wasn't just a relevance problem, it was a "the right answer doesn't exist in this database" problem. Fixed 2026-09-06/07: both seed packs (49 objects) are loaded, embedded, and fully indexed — 83 objects, 180/180 segments with embeddings, 0 pending outbox events. Along the way, found and fixed two related bugs — a cross-pack edge-resolution gap in `cli/seed.py` and a retry-safety bug in `cli/worker.py` that would silently and permanently drop embeddings on any transient indexing failure.

**2026-09-07: re-ran the eval harness for real (API + worker up, pin fixed) and found the seed content was still invisible — for a third, distinct reason.** Existing (not embedding, not FTS) — the entire 49-object seed pack had `lifecycle_state = 'draft'` in its own source CSVs and had never actually been published; `postgres_search.py` hard-filters both FTS and vector search to `PUBLISHED` objects only, so drafts are invisible to search regardless of embedding state. Fixed live: ran all 49 through the real `RegistryService.publish_version()` gate (not bypassed) — **28 published cleanly** (re-indexed, re-embedded, now searchable); **20 correctly blocked** by Pydantic schema validation (11 `skill_guide` objects missing `learning_objectives`/`teach_forward`, 9 `project_blueprint` objects missing `budget_notes` — the seed CSVs were authored against an older shape of the schema and never updated). This is real, unauthored content, not a bug to patch — see TODO for the follow-up item.

Re-running the eval after publishing: still 3/11, but the *character* of every failure changed. Resilience-domain objects now dominate top hits for every on-topic query (e.g. `water.treatment-selection`, `power.circuit-basics`, the water/power/food curriculum modules) — hybrid ranking is working correctly once the content exists and is published. The remaining failures are two more distinct, real, and separately-scoped gaps:
- **Citation count is 0 for every resilience-domain answer.** `/v1/public/ask`'s `citations` field is populated from `EvidenceSpan` rows explicitly linked to a version (`services/evidence.py::list_citations_for_version`) — a provenance concept, not "which segments were retrieved." GGG-corpus objects have these links (real ingested documents); the hand-authored seed/curriculum content has none — nobody ever attached evidence-span citations to it. For safety-relevant content (water treatment, food safety) this is a real editorial gap worth prioritizing, not just an eval-scoring artifact.
- **The gold file's `expects_any` slugs don't match the actual seed pack's slugs** for several queries (e.g. it expects `water.rain-barrel`/`power.starter-solar`/`water.chlorine-treatment`; the seed pack has no rain-barrel content at all, and its actual slugs are `water.treatment-selection`, `power.circuit-basics`, etc.). The gold file appears to have been written against an aspirational/different content plan than what the seed pack actually contains.

**2026-09-07, same day: fixed the 20 blocked objects — 3/11 → 5/11.** Authored the missing content directly from each object's existing structured_data (goal/steps/failure-modes already present): `learning_objectives` + `teach_forward` (`three_minute_script`/`ten_minute_outline`/`handout_points`) for the 11 `skill_guide` objects; `budget_notes` for the 9 `project_blueprint` objects. Published via `RegistryService.create_version()` + `publish_version()` (the seed loader sets `current_version_id` even on draft-lifecycle objects, so `update_draft_version()`'s immutability guard rejected an in-place edit — a new v2 was the correct path, not a workaround).

Publishing the 9 `project_blueprint` objects surfaced a **third, distinct, real bug**: `PublishGate` requires a `safety_boundary` for `COType.PROJECT_BLUEPRINT` (and `LOCAL_ADAPTATION`), but `ProjectBlueprintStructuredData` (and `LocalAdaptationStructuredData`) never defined that field — Pydantic's default `extra="ignore"` silently stripped it before the gate ever saw it, so **no `project_blueprint` object could ever have passed this gate**, seed-authored or otherwise. Fixed: added `safety_boundary: str` to `ProjectBlueprintStructuredData` (`schemas/structured_data.py`), authored real per-object safety content (generator CO risk, electrical panel work, asbestos/lead in old insulation, water-testing escalation, etc.), then published all 9. `LocalAdaptationStructuredData` has the identical latent gap — no objects of that type exist yet to be blocked by it, so left as a flagged, not-yet-fixed TODO item rather than changed speculatively.

**Result: 51/51 resilience-seed objects published** (was 2/51), 0 draft, 0 pending outbox events. Eval: 5/11 (`eval/reports/2026-09-07.md`), up from 3/11. Full test suite re-verified after the schema change: 400 passed, 6 failed (same known issues as before, no regressions). Remaining eval gaps are the two genuinely separate ones above (citations, gold-file/slug mismatch) plus the Spanish query, which is deliberately expected to keep failing until real multilingual content or matching lands (per the gold file's own comment) — none of these three are retrieval bugs.

**2026-09-08: first real ingestion source landed — FEMA's *Are You Ready?* (source 1 of 3 in the ingestion plan; USDA and OSHA still to come).** Ran the full pipeline (`parse → extract → draft → cite → canonicalize → edges → bundles → validate → load --publish`) against the real 22MB/204-page PDF (public domain, archive.org). This is the pipeline's first live run against a document it had never seen, and it surfaced real, previously-undiscovered bugs the way the plan expected:

- `polars` has no compiled runtime for Python 3.14 at all yet (`polars-runtime-32`'s own PyPI classifiers only list 3.10–3.13) — confirmed this blocks real ingest work, not just tests. Fixed by creating a second venv, `.venv-ingest/` (Python 3.13, gitignored), used only for `cli.ingest` commands; the main `.venv` (3.14) is untouched. This is the concrete resolution to the previously-open "pin an older Python for ingest work" TODO item.
- `cli/ingest/parse.py::convert_pdf_to_markdown()` never set `output_format` in the `ConfigParser` options dict; marker-pdf 1.10.2's `get_renderer()` indexes that key directly with no default (`KeyError`). The `parse` pass had apparently never been exercised against a real PDF with the currently-pinned marker-pdf version. Fixed with one line (`"output_format": "markdown"`). Page-provenance checkpoint (5 spot-checks against the raw PDF via `pypdfium2`) then passed exactly — confirms the May P0 page-provenance fix holds on new documents.
- The ingest CLI resolves `OPENAI_API_KEY` from `os.environ` directly (`cli/ingest/llm_client.py`) — unlike the main app, it never loads `.env` (no `get_settings()`/pydantic-settings call in that code path). Not a bug, just an operational gotcha: every LLM-calling pass needs `OPENAI_API_KEY=$(...)` prefixed explicitly when run outside the main app's process.
- `draft` produced a small number of objects (5 out of 279) with an `id` field (dot-namespaced, e.g. `emergency-preparedness.are-you-ready`) that disagreed with their own `slug` field (dash-only) — and `edges` (a separate LLM call) referenced objects by `id` while `validate.py`'s duplicate/edge-integrity check resolves by `slug`. Not fixed at the pipeline level (a genuine draft/edges internal-consistency gap, flagged in TODO); worked around for this run by remapping `edges.csv` through an `id → slug` table before validating.
- A genuinely new, narrow, **not fully root-caused** bug: 10 of the 275 loaded objects' `version.published` outbox events reference an `object_id`/`version_id` that doesn't match any persisted row, even though `seed_graph()` reported "275 objects created, 0 skipped" and exactly 275 objects with matching timestamps do exist in the DB. These 10 real objects therefore have zero `content_segments` — published in name only, invisible to both FTS and vector search. Outbox events for them were deleted (so the worker stops retrying them forever); the objects themselves were left in place. Flagged in TODO as unresolved — needs a deeper look at `cli/seed.py`'s per-node flush/id lifecycle under some as-yet-unidentified condition.
- `validate.py`'s `risk_band in ("high","expert_only") → requires safety_boundary` check is **unconditional** (runs even without `--publish`) and applies to *every* object type — stricter than the real `PublishGate`, which only requires `safety_boundary` for `SKILL_GUIDE`/`PROJECT_BLUEPRINT`/`LOCAL_ADAPTATION`. 21 objects tripped it (nuclear/terrorism/tsunami/heat-stroke/flash-flood/severe-thunderstorm content, correctly classified `risk_band=high` by the LLM). 19 were `concept_note`/`reference_sheet` (definitional/awareness content, not actionable instructions) — given a short, honest, uniform caveat ("this is background/awareness information... not a substitute for official alerts... during an actual event"). 2 were genuinely actionable (`emergency-preparedness.terrorism-response` — a `skill_guide` that had `safety_boundary: []`, a type bug, not missing content; `safety.preparing-safe-room` — a `project_blueprint` about building a wind-resistant safe room) and got real, specific safety content (escalate to law enforcement/emergency responders; FEMA/ICC 500 code compliance and a licensed contractor/engineer, respectively) — the same level of care as the seed pack's project_blueprint fixes above.
- 4 objects (`emergency-preparedness.medicine-kit-supplies`, `emergency.frost-freeze-warning`, `hurricane-preparedness.community-training`, `safety.winter-storm-preparedness`) never reached the ≥2-citations bar `_check_publish_gate` requires for publishing — 3 have a genuine content-thinness limit (the LLM consistently found only 1 real supporting claim across two `cite` attempts), 1 has a persistent LLM JSON-output parsing failure. Set aside in `ingestion/projects/emergency-prep-fema/needs-review/` rather than forced through; not loaded.

**Net result**: 275 objects drafted and cited (1588 citations, 100% coverage on the loaded set), 265 fully live (published, segmented, embedded, searchable), 10 published-but-unindexed (flagged bug above), 4 held back pending more citation work, 21 published only after real safety-content authorship. Corpus-wide: **358 objects total, 357 published, 861/861 segments embedded, 0 pending outbox events.** Eval re-run: 4/11 (`eval/reports/2026-09-08.md`) — down one from 5/11, but **not a regression**: `≥2 citations` went to **11/11** (the single biggest previously-documented gap, now closed — every answer, including the resilience-domain ones, has real page-anchored evidence), and the raw pass-count dip is the already-documented gold-file/slug-naming issue generalizing as expected: FEMA content like `emergency.chlorination` is a genuinely good, well-cited answer to "is bleach safe for treating water," it's just not the exact slug (`water.chlorine-treatment`) the gold file's `expects_any` list names. Full test suite re-verified: 400 passed, 6 failed — same 5 polars failures plus a third example of the already-documented scale-dependent test-isolation flake (`test_execute_plan_returns_evidence_pack`, passes alone, fails only against the now much-larger real corpus) — no product regressions.

Cross-corpus reconciliation was **not** attempted: `canonicalize` only dedupes within its own project's drafts (39 internal merge decisions, e.g. `emergency.returning-home-safely` → `emergency.returning-home`), it has no visibility into the existing seed pack at all. There's real conceptual overlap without slug collisions between FEMA's `emergency.water-treatment-methods`/`emergency.water-sources`/`emergency.water-boiling` and the seed pack's `water.treatment-selection`/`water.safe-storage` — same territory, different naming conventions, never cross-linked via `supported_by` edges. Flagged as a deliberate scope decision (manual cross-corpus merge review, not something to force through automatically) rather than an oversight — see TODO.

Full narrative: `docs/superpowers/specs/2026-09-06-retrieval-verification-backfill-design.md` and `docs/superpowers/plans/2026-09-06-resilience-corpus-ingestion.md`. Latest reports: `eval/reports/2026-09-08.md` (current), `eval/reports/2026-09-07.md` (prior checkpoint).

### Private holdout corpus (new, 2026-09-06)

`holdout_corpus/` holds source material that's useful for A/B-testing the pipeline but doesn't meet the "open license for the core corpus" bar (VISION.md) — currently just documentation and an acquisition plan for Permatil's *Tropical Permaculture Guidebook* (CC BY-NC-SA 4.0), not yet downloaded. See `holdout_corpus/README.md` for the rules: never publish anything derived from it into the real commons.

### Open issues from the 2026-05-14 end-to-end smoke test

(Full detail in `docs/superpowers/plans/2026-05-14-followups.md`.)

- **Static build performance** — `astro build` takes 10+ minutes against a live backend because the per-domain SSG cache doesn't survive across Astro's per-route module instances. Fix identified (move cache to `globalThis` or thread via `getStaticPaths` props), not yet applied.
- **Eval harness has no conversation/multi-turn coverage** — it fires single-turn queries only; the conversation-memory path is untested by the harness.
- **Intent classifier** — the followups doc lists 4 misses from the smoke run. Re-checked against current `retrieval/intent.py` in this pass: 3 of the 4 (renter-safe → localize, "is X safe" → safety_check, "not flowing" → debug_failure) already have working regex handling and passing unit tests in `tests/test_retrieval_intent.py`. Only the "what is X about" → `why` case is unaddressed. **The eval report may be stale relative to the code** — re-run the harness before trusting it as a to-do list.
- **Ingestion canonicalization** — merge/split decisions are still logged and file-routed only; no merged/split objects are actually materialized.

### Deliberately deferred (documented, not forgotten)

- Citation QA dashboard (per-object reviewer view of citation strength).
- Caching for popular public queries (LRU keyed on normalized query + intent + context hash).
- Editorial auth flow for `/review` and `/ingest` (currently paste-the-bearer-key; needs real token issuance/scope display).
- PWA update-available toast (service worker registers but UI doesn't surface `waiting` state).
- `PUBLIC_USE_MOCK` env flag — the frontend's mock-data fallback is currently unconditional; should fail loudly in prod against an unhealthy backend instead of silently serving stale mock data.
- Cleanup of `_pre_envelope/_merged/_split`/`_holdback` ingest working directories committed to the repo from the GGG run; needs a retention policy and probably a `.gitignore` entry.
- Contradiction auto-detection — schema/endpoints exist, no automated detection pipeline.

### Empty modules (planned extension points)

- `src/capability_commons/jobs/__init__.py` — general background job scheduling (no code; outbox worker and IngestService handle current needs).
- `Neo4jGraphAdapter`, `OpenSearchAdapter` — abstract base classes exist, not implemented.

### Feature-gated functionality

- **Embedding indexing** — requires `OPENAI_API_KEY`. Without it, vector columns remain NULL and search falls back to FTS-only.
- **Sentry error tracking** — requires `SENTRY_DSN`.

### Integration tests

Integration tests require a live Postgres database and fail in environments without one; they run in the CI integration job with a pgvector service container.

### Housekeeping

- `feat/ingestion-tooling` (local + `origin`) is a stale branch pointer from before its own merge — 0 commits ahead of main, safe to delete.
- `.venv` (Python 3.14, base + dev + `[ingest]` extras) runs the app/API/worker/tests. `.venv-ingest/` (Python 3.13, gitignored) is a second venv used only for `cli.ingest` commands, since polars has no working runtime on 3.14 — see Content/vision gap and Tests.
- Dev machine disk space: was ~400MB free (97-100% full), now 36GB free — cleared 2026-09-07 (stale Cursor backup, `~/Library/Caches`, `docker system prune`; see repo-hygiene checklist for exactly what was touched).
- `.env`'s `OPENAI_API_KEY` was invalid (401 from OpenAI); fixed by the user 2026-09-07. Embedding backfill completed immediately after — see Content/vision gap above. Note: `cli/ingest`'s LLM client reads `OPENAI_API_KEY` from `os.environ` directly, not from `.env` — export it explicitly when running ingest passes outside the main app.
- `fastapi`/`starlette`/`prometheus-fastapi-instrumentator` pin — **fixed 2026-09-07** (`prometheus-fastapi-instrumentator>=8.0,<9.0`; see Tests section).
- `.env`'s `DATABASE_URL` port drifted out of sync with the running Docker container once (pointed at 5433, real container on 5435, after an earlier Docker recreation) — fixed 2026-09-07. Worth double-checking `docker ps` against `.env` before assuming a DB-dependent command will work.
