# Follow-ups after the PLAN.md P0 / P1 / Stretch landings

Generated 2026-05-14, after PRs CapabilityCommons #2, #4 and
CapabilityCommonsSite #1, #3 all merged to main.

## Issues uncovered during the end-to-end smoke

### S1 — `astro build` slow against live backend
`src/pages/domains/[domain].astro` calls
`listPublicObjectsByDomain(domain)` for each of the 7 domains.
The cached graph payload (`getCachedGraphData`) and
`listPublicObjects()` *should* be shared across the build, but
each domain SSG hit takes ~16s in practice, blowing the static build
out to 10+ minutes against a real API.

**Hypothesis**: Astro spins a fresh module instance per page during
SSG, so the module-scope `_cachedGraph` doesn't survive across
routes. The static build effectively re-fetches per domain.

**Fix**: move the cache to an Astro `globalThis`-keyed cache or use
`getStaticPaths`'s `props` to pass the data in once. Tiny patch
inside `src/lib/api.ts` and the four pages that call into it.

**Workaround today**: `astro dev` works fine; production builds
against an empty/mock backend stay fast.

### S2 — `/v1/public/metrics/quality` shows 0 conversations after eval run
The eval harness fires 11 queries but doesn't pass a
`conversation_id`, so no `ConversationTurn` rows are created. The
quality dashboard correctly shows `unique_conversations: 0` but a
reader might think the round-trip is broken.

**Fix**: in `eval/README.md`, document that the harness intentionally
sends single-turn queries. Optional follow-on: add a `--conversation`
flag that threads turns through a stable id so the harness exercises
the memory path too.

### S3 — All eval runs end `budget_exhausted` against the GGG corpus
14 of 15 retrieval runs landed `budget_exhausted` (sufficiency score
below the default 0.5 threshold). This is **correct** behavior — the
GGG-2026-03 newsletter is a finance corpus and the PLAN-canonical
queries ask about water / solar / food / refrigeration. The system
is honestly reporting "we don't have this content".

**Fix**: nothing to fix in the code. Either:
- Ingest a resilience-focused corpus that actually contains the
  PLAN-canonical content; or
- Trim the gold set to queries we have content for, and grow it
  back as the corpus widens.

### S4 — Intent classifier misses several PLAN-canonical queries
EVAL-1 reported `intent_correct: 7/11`. The four misses are
informative:

| Query | Expected | Got |
|---|---|---|
| "Renter-safe food resilience" | `localize` | `how_to` |
| "Why is my rain barrel system not flowing?" | `debug_failure` | `how_to` |
| "Is bleach safe for treating drinking water?" | `safety_check` | `how_to` |
| "What is the gold-goats-guns portfolio about?" | `why` | `how_to` |

**Fix**: tighten the regex patterns in
`src/capability_commons/retrieval/intent.py`. In particular:
- "safe for ..." should fire `SAFETY_CHECK` (currently the regex
  requires `\bsafety\b` or specific lookbehind).
- Bare "why ... about?" should fire `WHY`.
- "renter-safe" or "X-safe" (without "is") should fire `LOCALIZE`,
  not `SAFETY_CHECK`.
- "not flowing", "won't ...", "stopped" should fire `DEBUG_FAILURE`;
  the regex is there but the query stems differently.

Each pattern bump should land with a new test in
`tests/test_retrieval_intent.py`.

## Known TODOs we deliberately deferred

### From PLAN.md "Days 76-90"
- **Citation QA dashboard**. We surface citation precision in
  `/v1/public/metrics/quality` but there's no per-object QA view
  where a reviewer can spot-check the strength of each citation.
- **Cache popular public queries**. `RetrievalRun` rows are
  persistent but each `/v1/public/ask` call still re-runs the planner.
  An LRU keyed on `(normalized_query, intent, context_hash)` would
  shave latency on hot queries.

### Frontend follow-ons
- **Editorial flow**. `/review` and `/ingest` are bearer-token surfaces
  with a paste-the-key login. A proper auth flow (token issuance,
  scope/role display, sign-in via the API) is the next step before
  exposing these to outside reviewers.
- **`/print/[slug]` static fan-out**. Currently SSG-ed but the
  `getStaticPaths` pulls every `listPublicObjects()` entry — fine
  until the corpus grows. Same caching fix as S1 applies.
- **PWA install prompts and update toasts**. Service worker registers
  but the UI doesn't acknowledge it. A small "app update available"
  toast when the SW reports `waiting` would be nice.

### Backend follow-ons
- **Cleanup of `_pre_envelope/_merged/_split` ingest holdback dirs**.
  Committed to the repo because the GGG run produced them; should
  probably gitignore those subpaths going forward and document the
  retention policy.
- **`_holdback/` legacy YAML on the ingest project**. We kept
  `finance.portfolio-holdings-table.yaml` out of the publish set
  because it had <2 citations. Either re-cite and re-publish, or
  delete with intent. Currently sits in repo limbo.
- **`PUBLIC_USE_MOCK` env flag**. The mock-fallback path in
  `src/lib/api.ts` is unconditional. Wrap it in an env flag so prod
  builds with an unhealthy backend fail loudly instead of silently
  serving stale mock data.

## Process notes

- Both PR stacks (#2→#4 and #1→#3) were merged sequentially. When
  the base PR is merged first, the stretch PR's branch gets orphaned
  and the PR auto-closes; the workaround is to re-create the PR
  against `main`. A cleaner stacked-PR workflow (graphite,
  spr-cli, or just merging in one go via squash-merge of the stretch
  branch into main) is worth setting up before the next multi-stack
  push.
- `gh auth login` is required for any of this. We hit a missing-auth
  error on the first attempt; documented in PR descriptions but
  worth pinning in `CONTRIBUTING.md`.
- `astro build` taking 15+ seconds per page when the live backend is
  reachable is currently a productivity sink. The dev server works
  fine; production builds should target a fast (cached) backend or
  the mock fallback.

## Quick-start for the next session

```bash
# Backend
cd CapabilityCommons
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn capability_commons.main:app --host 127.0.0.1 --port 8123 --log-level warning &
export OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)
.venv/bin/python -m capability_commons.cli.worker --poll-interval 2 &

# Run the eval harness
.venv/bin/python -m capability_commons.cli.eval run \
    --gold eval/gold/queries.yaml \
    --api  http://127.0.0.1:8123 \
    --out  eval/reports/$(date +%Y-%m-%d).md

# Site
cd ../CapabilityCommonsSite
PUBLIC_API_URL=http://127.0.0.1:8123 npx astro dev --host 127.0.0.1 --port 4321
```

## Where things sit

| Repo | Branch | State |
|---|---|---|
| CapabilityCommons | main | PLAN.md P0/P1 + stretch merged. 365 unit tests passing. |
| CapabilityCommonsSite | main | Feature-complete + stretch merged. `astro check` clean. |
