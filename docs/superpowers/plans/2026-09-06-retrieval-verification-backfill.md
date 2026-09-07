# Plan: Retrieval Verification & Embedding Backfill

Design: [2026-09-06-retrieval-verification-backfill-design.md](../specs/2026-09-06-retrieval-verification-backfill-design.md)

## Step 1 — stand up a dev environment (shared blocker) — ✅ done 2026-09-06

- [x] `.venv` created, base + dev deps installed (`pip install -e '.[dev]'` plus `greenlet`, which turned out to be a missing transitive dependency — SQLAlchemy async raised `ValueError: the greenlet library is required` without it; worth adding explicitly to `pyproject.toml`'s base `dependencies`).
- [x] Found and restarted `capabilitycommons-db-1`, a stopped container from ~4 months ago with its original data volume (`capabilitycommons_pgdata`) intact — recreated on port 5435 (5433 is now used by an unrelated project's container on this machine) since the volume persists independent of the container. This is the real historical database, not a fresh reconstruction.
- [x] Migrations already at head (`20260504_0001`) — no `alembic upgrade` needed.
- [ ] `[ingest]` extras (marker-pdf, polars, rich, aiofiles, tiktoken, rapidfuzz) **not installed** — `pip install` failed with "No space left on device." The machine has ~650MB free on a 460GB disk. This blocks `test_ingest_*.py` collection and any actual ingestion pipeline run (including the resilience-corpus plan) until disk space is freed. Flagged in the repo-hygiene checklist — this is a machine-level issue, not a repo bug.
- [x] `.venv/bin/pytest tests/ -q` run against the real database: **316 passed, 42 failed.** See the design doc's "What actually happened" section for the failure breakdown (a new FastAPI/starlette/prometheus-instrumentator version-drift bug accounts for ~34 of them). The 346/365 figure carried in STATUS.md was in the right range but not exactly reproduced — some of that gap is the missing `[ingest]` extras (4 test files can't even collect) and some is the newly-found dependency-drift bug.

## Step 2 — re-run the eval harness — not done

Blocked on the FastAPI/prometheus-instrumentator issue found in Step 1 (the API app fails to instantiate cleanly for anything touching Prometheus middleware) and the invalid `OPENAI_API_KEY` (Step 3). Do this after both are resolved:

- [ ] Either fix the version pin or set `METRICS_ENABLED=false` as a workaround to start the API
- [ ] Start the API + worker per the quick-start in `docs/superpowers/plans/2026-05-14-followups.md`
- [ ] `python -m capability_commons.cli.eval run --gold eval/gold/queries.yaml --api http://127.0.0.1:8100 --out eval/reports/<today>.md`
- [ ] Diff the intent-match column against `eval/reports/2026-05-14-smoke.md`, specifically the 4 S4 queries
- [ ] Update `docs/superpowers/plans/2026-05-14-followups.md`'s S4 section: mark resolved items resolved, keep only what's still genuinely broken

## Step 3 — check embedding NULL-ness on seed objects — ✅ done 2026-09-06, different root cause than hypothesized

- [x] Queried `content_segments` directly: **the seed pack wasn't NULL-embedded, it wasn't loaded into the database at all.** Only the 34 GGG objects existed (129/129 segments embedded — fully healthy). Loaded both seed packs (49 objects total) via `python -m capability_commons.cli`.
- [x] Root-caused *why* new content would get stuck without embeddings even after loading: `cli/worker.py`'s outbox processor marked every event `processed_at` regardless of handler success. Confirmed live against the actually-invalid `OPENAI_API_KEY` in `.env` (401 from OpenAI). **Fixed** — see the design doc.
- [x] Recorded the real finding in the design doc, replacing the hypothesis language.

## Step 4 — build the backfill job — not needed; fixed at the source instead

The original plan was a bespoke `capability_commons.cli.backfill embeddings` command. Given the actual root cause (Step 3), that's no longer necessary: the worker fix means a failed indexing attempt now retries automatically on the next poll instead of being silently and permanently marked done. The 51 events stuck by the pre-fix code were manually reset to unprocessed (`UPDATE outbox_events SET processed_at = NULL WHERE ...`) so they're already queued for retry. **All that's left is a valid `OPENAI_API_KEY` and restarting the worker** — flagged as the resource this session needs sourced.

## Step 5 — query caching

- [ ] LRU (or Postgres-backed, if process-local LRU won't survive multiple API workers) keyed on `(normalized_query, intent, context_hash)`
- [ ] Cache key includes something that changes on republish (e.g. a max `updated_at` over the objects in the result set, or a global "corpus version" counter) so a content update doesn't serve a stale cached answer
- [ ] Test: same query twice returns the cached result on the second call; a publish event in between invalidates it

## Step 6 — multilingual wiring scope-out

- [ ] Confirm the Spanish gold query still fails with "no matching results" (the intentionally-correct failure mode per the gold file's own comment) rather than erroring
- [ ] Write up (doesn't need to be built now) what full `language_code` wiring requires: per-language FTS config in Postgres (`websearch_to_tsquery` takes a language config name), whether embeddings are language-agnostic enough to cross-match, and where translated content would need to live in the object model — feeds into the existing "Translation workflow" TODO item rather than duplicating it
