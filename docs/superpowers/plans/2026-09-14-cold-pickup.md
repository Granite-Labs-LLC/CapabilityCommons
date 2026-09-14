# Cold Pickup: Capability Commons (as of 2026-09-14)

Start here if you're picking this project up with no prior context. It covers the current state, how to run things, every remaining piece of work, and — for each item — what blocks it and what unblocks it. `TODO.md` and `STATUS.md` have the long-form history; this document is the working queue.

Status markers used below: **Ready** (unblocked engineering, can start now), **Blocked** (needs a person, decision, secret, or another task first), **Decision** (needs an owner's call, no engineering until then).

---

## 1. State of the world

**Code and CI**
- `main` is the only active branch. CI (`.github/workflows/ci.yml`) has six jobs: `lint`, `typecheck`, `test`, `ingest-tests` (new 2026-09-14, Python 3.13), `integration` (real Postgres), `docker`, plus an informational `eval` job that no-ops without an `OPENAI_API_KEY` repo secret. CI on the 2026-09-14 commits (`d2b34bf`): all jobs green, including the new `ingest-tests` job on its first run.
- `Deploy` (`.github/workflows/deploy.yml`) fails on every push: its secrets were never set (see B1).
- Full local test suite (2026-09-14, excluding the 4 ingest files): **364 passed, 0 failed** (6m40s). Ingest files under `.venv-ingest`: 72 passed.

**Corpus** (local dev database only — nothing is deployed)
- Four ingested sources: FEMA *Are You Ready?* (2026-09-08), USDA *Complete Guide to Home Canning* (2026-09-13), OSHA 3075 *Controlling Electrical Hazards* (2026-09-13), plus the older off-mission GGG finance newsletter. Plus two hand-authored seed packs (`expanded_seed/`, `capability_commons_module_seed_pack_v1/`).
- 403 objects published, every one embedded and searchable. **54 held `in_review`** (44 USDA, 10 OSHA) awaiting human review (B2). 1 draft.
- Eval (`eval/gold/queries.yaml`, 16 queries as of 2026-09-14): **10/16**, ≥2 citations 16/16, intent correct 13/13 (`eval/reports/2026-09-14.md`, local only). 4 of the 5 new canning/electrical queries pass; "overhead power lines" fails as expected because its only good answer is held `in_review` (B2). Still failing from before: drinking water during an outage (retrieval ranks FEMA content above `water.safe-storage`), rain-barrel and solar-fridge (no such content), off-grid refrigeration learning path, and the Spanish query. The previous day's 6/11 was on the older 11-query set.

**Frontend** (`apps/site`, a git submodule → `Granite-Labs-LLC/CapabilityCommonsSite`)
- Astro static site, builds in ~3 minutes against a live backend (1,000+ pages). As of 2026-09-14, a production build fails loudly if the backend is unreachable instead of silently shipping mock data (`PUBLIC_USE_MOCK`).
- A local-only branch `backup-local-unpushed-fe-work` holds a superseded frontend lineage. Don't delete it without the owner (D4).

---

## 2. Running things locally

```bash
# Database: Docker container on port 5435 (NOT 5432/5433). Check .env's DATABASE_URL matches `docker ps`.
docker ps --filter name=capabilitycommons-db-1

# App, API, worker, tests: Python 3.14 venv
.venv/bin/uvicorn capability_commons.main:app --host 127.0.0.1 --port 8100
.venv/bin/python -m capability_commons.cli.worker          # embeds published objects via the outbox
.venv/bin/python -m pytest tests/ --ignore=tests/test_ingest_draft_schema.py \
  --ignore=tests/test_ingest_llm_client.py --ignore=tests/test_ingest_passes.py \
  --ignore=tests/test_ingest_publish_gate.py

# Ingestion: separate Python 3.13 venv (polars/marker-pdf have no 3.14 wheels)
export OPENAI_API_KEY="$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)"   # export only this one
.venv-ingest/bin/python -m capability_commons.cli.ingest <pass> <project>
.venv-ingest/bin/python -m pytest tests/test_ingest_*.py

# Eval (API must be running and idle -- see gotcha G4)
.venv/bin/python -m capability_commons.cli.eval run --gold eval/gold/queries.yaml \
  --api http://127.0.0.1:8100 --out eval/reports/$(date +%F).md

# Frontend
cd apps/site && PUBLIC_API_URL=http://127.0.0.1:8100 npx astro build
```

---

## 3. Decisions already made — don't relitigate

| Decision | Made by | Where recorded |
|---|---|---|
| Ingestion holds `high`/`expert_only` objects `in_review` instead of publishing (matches the API's `PublishGate`). **New loads only**: FEMA's 55 high-risk objects published on 2026-09-08 were deliberately left live. | Project owner, 2026-09-13 | `TODO.md`, commit `c31c6d9` |
| 44 USDA pressure-canning / low-acid / botulism objects raised to `high`, each with safety text quoted from the guide. | Project owner, 2026-09-13 | `ingestion/projects/resilience-usda-canning/logs/risk-reclassification-2026-09-13.md` |
| OSHA 3075 limited to its hazard-guidance pages 1–24 (pages 25–71 are OSHA agency programs and office directories). | Engineering, 2026-09-13 | `ingestion/projects/resilience-osha-electrical/logs/scope-filter-2026-09-13.md` |
| OSHA's own `high` ratings kept as drafted (including some background concept notes); a reviewer may downgrade them. | Engineering, 2026-09-13 | `.../resilience-osha-electrical/logs/safety-boundaries-2026-09-13.md` |
| Adopted `origin/main` for the frontend submodule; the old local lineage is preserved on a backup branch. | Project owner, 2026-09-13 | commit `07281de` |
| CI eval is informational (`continue-on-error`) and costs nothing until a secret is added. | Engineering, 2026-09-13 | `ci.yml` comment |
| Don't ingest Mollison/Holmgren/Fukuoka (commercially copyrighted); Permatil is CC BY-NC-SA and only usable as a private holdout. | Engineering research, 2026-09-06 | `holdout_corpus/README.md` |

---

## 4. Work queue

### A. Ready — unblocked engineering

Ordered roughly by value. Each has enough context to start cold.

| # | Task | Why it matters | Where to start | Done when |
|---|---|---|---|---|
| A1 | **Speed up `/v1/public/objects`** | Renders every published object one at a time with ~6 queries each (N+1). Took >60s at 382 objects; it's the dominant cost of the site build and will get worse with every source. | `publication/service.py::list_published_objects` → batch facets, entities, citations, reviews, contradictions per page of objects | List endpoint returns 400+ objects in a few seconds; site build time drops |
| A2 | **Retry the FEMA object whose `cite` pass failed on JSON parsing** | `safety.winter-storm-preparedness` has never been cited because the model's JSON output failed to parse. `draft` now saves raw failures; `cite` doesn't. | Add the same raw-output logging to `cli/ingest/cite.py` as `draft.py` has (`logs/*-failed.<slug>.json`), then `cite emergency-prep-fema --slugs safety.winter-storm-preparedness` | Object has ≥2 citations and can load, or its raw failure is logged and understood |
| A3 | **Isolate the scale-dependent flaky test** | `test_execute_plan_returns_evidence_pack` passes alone and fails against the real corpus: its seeded object shares the real workspace and gets outranked. | Give it its own `test-%` workspace (the `workspace` fixture) and query within it | Passes in the full suite regardless of corpus size |
| A4 | **Close the testing gaps** | No coverage for: full retrieval plan→execute→assemble; publication bundle and learning-path rendering; `PostgresSearchAdapter.fetch_segments()`. | `tests/test_integration_retrieval.py`, `tests/test_integration_publication.py`, `tests/test_integration_search.py` | One integration test each, in CI |
| A5 | **Derive the site's stats instead of hard-coding them** | `apps/site/src/lib/config.ts` `STATS` says 49 objects / 175 edges; the corpus has 403 published. Shown on the stats strip, `/status`, and `/offline`. | Compute from `listPublicObjects()` / `getCachedGraphData()` at build time | Numbers match the backend at build |
| A6 | **Stop `seed_graph()` publishing `draft` nodes** | It sets `published_at` and emits `version.published` even when a node declares `lifecycle_state: draft` (only high-risk objects are now exempt). Search filters on lifecycle, so the effect is wasted indexing and misleading timestamps, but it confused a 2026-09-07 session. | `cli/seed.py`, node loop; check the CI `eval` job's seeding still behaves (seed packs declare `draft`) | Draft nodes load as draft with no publish event; integration test |
| A7 | **Decide what to do about `project_blueprint.phases`** | Validation warns on every blueprint because drafts never populate `phases`. Either the prompt should ask for it or the warning should go. | `cli/ingest/validate.py` (warning), `draft.py` `USER_TEMPLATE` | No warning on a clean run |
| A8 | **Query caching** | Every `/v1/public/ask` re-runs the planner (3–4s locally). | Spec: `docs/superpowers/plans/2026-09-06-retrieval-verification-backfill.md` Step 5 — key on `(normalized_query, intent, context_hash)` plus a corpus-version counter so republishing invalidates | Repeated queries return from cache; publish invalidates |
| A9 | **Multilingual search** | `language_code` exists but isn't wired through ranking/synthesis; the Spanish gold query fails end-to-end. | `search/adapters/postgres_search.py`, `retrieval/` | Spanish gold query passes against Spanish or translated content |
| A10 | **Cross-corpus duplicate *proposals*** | `canonicalize` only compares drafts within one project, so FEMA/USDA/seed-pack food and water overlap was never surfaced. The *decision* is human (B5), but tooling to propose candidate pairs is engineering. | Reuse `canonicalize.find_similar_groups` against published objects from the DB; output a review list, change nothing | A report of likely cross-source duplicates exists for an editor |
| A11 | **Frontend verification pass** | Unchecked against the current corpus: six-part bundle rendering, D3 graph explorer at 400+ nodes, and the manual end-to-end smoke. | `docs/superpowers/plans/2026-09-06-frontend-build-and-polish.md` §4 | Each item confirmed or bugs filed |
| A12 | **PWA update-available toast** | Service worker registers but never tells the user a new version is waiting. | Same plan, §3 | Toast appears when a new build is deployed |
| A13 | **Eval `--conversation` flag** | The harness only sends single-turn queries, so the conversation-memory path (and `/v1/public/metrics/quality` conversation counts) is never exercised. | `cli/eval.py`; document the single-turn default in `eval/README.md` | Multi-turn mode exists and is documented |
| A14 | **Make the red `Deploy` run quieter (optional)** | `Deploy` fails on every push to `main` until B1 is done, which trains people to ignore red. Could skip when `DEPLOY_HOST` is unset, the way the `eval` job does. Trade-off: a silently skipped deploy can hide a misconfiguration. | `.github/workflows/deploy.yml` | Owner agrees to the trade-off first |
| A15 | **Tier 3 platform work** (large, not urgent) | Offline export (PDF/EPUB), low-bandwidth static mirror, print-ready field guides; contradiction detection (narrow same-domain heuristic first). | `TODO.md` Tier 3; `docs/superpowers/plans/2026-09-06-editorial-trust-tooling.md` §3 | Per item |

Not needed until scale demands it: Neo4j graph adapter (~10k+ nodes), OpenSearch adapter, read replicas.

### B. Blocked — needs a person, secret, or another task first

| # | Task | Blocked by | Who unblocks | Once unblocked |
|---|---|---|---|---|
| B1 | **Deployment (staging, then production)** | Repo secrets never set: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH` (per GitHub environment `staging`/`production`). Failure reads `error: missing server host`. | Whoever owns the deploy target | Push to `main` deploys staging; run `workflow_dispatch` for production. Then set the site's production `PUBLIC_API_URL`, build, and run the smoke checks in A11 against the real host. Unblocks public launch. |
| B2 | **Review and publish the 54 held objects** | Needs qualified human reviewers — for USDA, someone who can check processing times and pressures against the guide's tables. Scaling past one operator also needs B3. | Project owner / recruited reviewers | For each: `POST /v1/reviews` with `outcome: approved` (moves it to `reviewed`), then `POST /v1/objects/{object_id}/versions/{version_id}/publish` (the publish gate requires that approved review; publishing emits the event the worker embeds). Lists: `ingestion/projects/resilience-usda-canning/logs/risk-reclassification-2026-09-13.md` and `.../resilience-osha-electrical/logs/safety-boundaries-2026-09-13.md`. Unblocks: 2 of the new gold queries (green beans, overhead lines) and the live pressure-canning content. |
| B3 | **Editorial auth flow** (then citation QA dashboard) | Needs a product decision on the reviewer model: roles/scopes on the existing `api_keys` table vs. something new, and invite/sign-in UX. | Project owner | Spec: `docs/superpowers/plans/2026-09-06-editorial-trust-tooling.md` §1–2. Do auth first (it gates who can use review tools), then the citation QA dashboard, dogfooded on the USDA/OSHA batch. |
| B4 | **CI eval actually running** | `OPENAI_API_KEY` repo secret not set — a billing decision (seeding and embedding costs money every push). | Repo billing owner | Job starts running. Follow-up engineering at that point: the job seeds only the hand-authored packs, so load the committed ingestion outputs (`ingestion/projects/*/output`) too, or the CI score won't reflect the real corpus. |
| B5 | **Cross-corpus deduplication decisions** | Editorial judgment: which FEMA/USDA/seed-pack objects are duplicates to merge vs. complementary objects to link with `supported_by` edges. | Editor / project owner | A10 produces the candidate list; apply decisions as edges or merges. |
| B6 | **4 FEMA objects in `needs-review/`** | 3 have only one real supporting citation (content-thin; the model found no more across two attempts). The 4th is A2. | Editor (add citations by hand or drop them) | Load them via `ingest load emergency-prep-fema --publish`. |
| B7 | **Secret management** | Infrastructure choice (Vault, AWS SSM, platform-native). Currently `.env`. | Infra owner | Move `OPENAI_API_KEY`, `DATABASE_URL`, API key seeds out of `.env`. |
| B8 | **Community workflows** — contributor attribution, local adaptation submissions, field-test results affecting lifecycle, translations (`TRANSLATED_FROM` edges) | Product design; the backend endpoints `/v1/contribute/adaptation` and `/v1/contribute/field-report` exist, the process around them doesn't. | Project owner | Per `TODO.md` Tier 3 "Community infrastructure". |
| B9 | **Tier 4 learning/AI features** — adaptive paths, assessment engine, progress tracking, cohorts, personalized retrieval, tutor memory, quality scoring, cross-source contradiction detection | Product priorities; most also want real users and reviewed content first (B1, B2). | Project owner | See `TODO.md` Tier 4. |
| B10 | **Private holdout A/B benchmark** (Permatil *Tropical Permaculture Guidebook*) | Licensing is fine for private use only; the download is gated behind the publisher's shop. | Project owner | Rules in `holdout_corpus/README.md`: never publish anything derived from it. Chapter 7 is the suggested first slice. |
| B11 | **More sources: architecture / owner-building** | No strong openly licensed source found yet. | Research | Same pipeline once a source is chosen; follow `ingestion/README.md`'s operational notes. |

### D. Decisions only (no engineering until made)

| # | Decision | Context |
|---|---|---|
| D1 | Delete the stale `feat/ingestion-tooling` branch (local and `origin`)? | 0 commits ahead of `main`; deleting the remote branch is outward-facing, so it waits for the owner. Command in `docs/superpowers/plans/2026-09-06-repo-hygiene-checklist.md`. |
| D2 | Retention policy for ingestion scratch directories (`_merged/`, `_split/`, `_holdback/`, `_pre_envelope/`) | All four projects commit them today, with source PDFs. Decide whether to keep them in git or `.gitignore` future runs. |
| D3 | `ggg-2026-03/.../_holdback/finance.portfolio-holdings-table.yaml` | Held back for <2 citations. Re-cite and publish, or delete deliberately. |
| D4 | Keep or delete `apps/site` branch `backup-local-unpushed-fe-work` | The only copy of a superseded frontend lineage. |
| D5 | Stacked-PR workflow | Merging a stack's base PR first once auto-closed the stretch PR. Options: graphite, spr-cli, or squash-merge instead of stacking. |
| D6 | Should OSHA's `high`-rated background notes be downgraded before or during review? | Engineering kept the model's ratings (conservative). |
| D7 | **How does the static site build get past the API's public rate limit?** Blocks any real production build (B1). | With auth enabled (default), `/v1/public/*` allows 60 requests/minute per IP; a build makes one bundle request per object — 422 in one minute locally — so most return `429`. Before 2026-09-14 those silently fell back to mock data, so earlier "successful" builds very likely shipped mock pages. Options: an unlimited API-key scope sent by the build (non-`PUBLIC_` env var, so it isn't exposed to browsers), an IP allowlist, or honouring `Retry-After` (slow: ~10 min/build). Security trade-off → owner decides; then implement in `api/rate_limit.py` + `apps/site/src/lib/api.ts`. Also switch `rings.astro`/`search.astro` to `getCachedGraphData()`. |

### Dependency chains at a glance

- **Launch:** B1 deploy secrets **and** D7 build-vs-rate-limit decision → staging deploy + real site build → A11 smoke against the real host → production deploy → public launch.
- **Reviewed canning/electrical content:** B3 editorial auth (to scale beyond one operator) → B2 reviews → held objects publish → the green-beans and overhead-lines gold queries can pass.
- **Trustworthy eval gate:** B4 secret → CI eval runs → load ingestion outputs in CI → enough stable runs to trust the gold set → consider making eval a merge gate.
- **Duplicate cleanup:** A10 proposals → B5 editorial decisions → merges/edges applied.

---

## 5. Gotchas that have cost real time

- **G1 — Two venvs.** App/API/worker/tests use `.venv` (3.14); ingestion uses `.venv-ingest` (3.13). Installing `[ingest]` into `.venv` fails.
- **G2 — `OPENAI_API_KEY` isn't read from `.env` by the ingest CLI.** Export only that variable; `export $(cat .env)` breaks `CORS_ORIGINS` parsing.
- **G3 — `parse`, `validate`, and `load` reject `--yes`.** The LLM passes accept it. Run long passes with `nohup ... < /dev/null > log 2>&1 &`; tool timeouts killed a parse once.
- **G4 — Don't run eval during or right after a site build against the same API.** On 2026-09-14 eval scored 0/16 twice for two different reasons, neither a code regression: first every `ask` timed out while the build loaded the single-process API; then, run right after the build, every `ask` got `429` because the build had used up the 60/minute public rate limit for 127.0.0.1 (see D7). Run eval on an idle API, in a fresh minute. For local builds, start the API with `AUTH_ENABLED=false` (disables rate limiting) or the build will fail. A third run still scored 1/16: the harness fired all 16 queries at once, and against one API process each `ask` waited behind the rest (median ~2s alone vs 25–35s all at once, past the 30s timeout). A controlled comparison of `e4a0c9d` vs `d2b34bf` (alternating order, three concurrent rounds each) showed no difference between the versions, so it wasn't a regression. The harness now runs at most 4 queries at a time (`3ecdeff`), which scored 10/16.
- **G5 — Integration tests share the dev database.** Tests using the real `capability-commons` workspace (e.g. `seed_graph()`) must clean up after themselves; `conftest.py` only cleans `test-%` workspaces. `outbox_events` has no foreign keys, so leftover events retry forever. The FEMA "orphaned events" mystery was this.
- **G6 — Check the risk-band distribution before `load --publish`.** The model under-rated canning and over-rated electrical background notes. `high` objects need `safety_boundary` or validation blocks the load, and they'll load `in_review`.
- **G7 — The model rewrites things it shouldn't.** Slugs (now forced to the matrix slug), enum values (now listed in the prompt), invented time/cost estimates (prompt says null unless sourced), nested fields (now shown as a JSON example). When a pass fails systematically, read the raw output before retrying.
- **G8 — `.env` `DATABASE_URL` drifts from the container port.** It's 5435.
- **G9 — `eval/reports/` is gitignored.** Reports referenced in docs live only on the machine that ran them.

---

## 6. Where the detail lives

- `TODO.md` — full tiered backlog with history per item.
- `STATUS.md` — component status and a narrative of each session's findings.
- `docs/superpowers/plans/2026-09-06-resilience-corpus-ingestion.md` — per-source ingestion outcomes.
- `docs/superpowers/plans/2026-09-06-editorial-trust-tooling.md` — editorial auth, citation QA, contradiction detection.
- `docs/superpowers/plans/2026-09-06-frontend-build-and-polish.md` — frontend verification and PWA toast.
- `docs/superpowers/plans/2026-09-06-retrieval-verification-backfill.md` — query caching spec.
- `docs/superpowers/plans/2026-09-06-repo-hygiene-checklist.md` — housekeeping decisions.
- `ingestion/README.md` — operator guide plus lessons from real runs.

---

## 7. Done on 2026-09-14 (this document's session)

| Commit | Change |
|---|---|
| `50b86e2` | Engine no longer reuses pooled connections across event loops (the "two TestClients in one process" bug) |
| `ba26ce4` | CI: new `ingest-tests` job on Python 3.13; app tests back in the main integration run |
| `cc6dd42` | `canonicalize` validates merged/split objects and never lowers risk or drops safety text |
| `185d7fe` | Evidence sources get real titles/kinds from the manifest; `NO_SUPPORT` placeholders no longer become fake citations |
| `21dfa5f`, `3dc7134` | "What is X about" classified as `why` — and then the real fix: `/v1/public/ask` used a second, separate intent classifier that was wrong on 5 of 27 gold/test queries; both now share `infer_intent()` (eval intent 9/13 → 13/13) |
| `4fe769f` | 5 canning and electrical-safety gold queries |
| `d2b34bf` | README/CONTRIBUTING: Python 3.13 ingest venv, run-time gotchas, `gh auth login` |
| `3ecdeff` | Eval harness runs at most 4 queries at a time, so timeouts don't masquerade as retrieval failures (1/16 → 10/16 on the same code) |
| site `cd1a06c`, pointer `023b7c3` | Production site builds fail loudly instead of shipping mock data (`PUBLIC_USE_MOCK`). Verified: dead backend → build fails (`ECONNREFUSED`); live API with rate limiting off → 1,234 pages in 6m30s, no API errors (was ~3 min when failures silently fell back to mock) |

Local data fixes (dev DB only): backfilled real titles/kinds on the 4 ingested evidence sources; deleted the fake `NO_SUPPORT` source and its 3 spans.

Found along the way: D7 (site build vs. rate limit, and the likely mock content in earlier builds).
