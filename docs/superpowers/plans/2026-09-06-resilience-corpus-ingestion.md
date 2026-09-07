# Plan: Resilience Corpus Ingestion

Design: [2026-09-06-resilience-corpus-ingestion-design.md](../specs/2026-09-06-resilience-corpus-ingestion-design.md)

Runs three public-domain sources through the pipeline in sequence, each with a review checkpoint, so a bad run on source 1 doesn't compound into sources 2 and 3.

## Pre-flight (blocking)

- [ ] Confirm or run the embedding backfill for the 49 existing seed objects (see the retrieval-verification plan). If skipped, note it explicitly in the eval comparison at the end of this plan so a bad score isn't misread as "the new content is irrelevant" when it's really "seed objects are structurally disadvantaged in RRF."
- [ ] Confirm `OPENAI_API_KEY` and a running outbox worker (`python -m capability_commons.cli.worker`) before any `load --publish`, or new content will hit the same NULL-embedding problem.
- [ ] `pip install -e '.[ingest]'` if not already done (marker-pdf, polars, rich, aiofiles, tiktoken, rapidfuzz).

## Source 1: FEMA — Are You Ready?

1. Download the PDF from `archive.org/details/FemaEmergencyHandbook-areYouReady` (or the `.mil` mirror found this session) to `ingestion/projects/`.
2. `python -m capability_commons.cli.ingest init emergency-prep-fema --source <path>.pdf --source-id src.fema.are-you-ready.2004 --source-title "Are You Ready? An In-Depth Guide to Citizen Preparedness" --source-kind BOOK`
3. `parse` → **checkpoint**: spot-check 5 segments' `page_start`/`page_end` against the actual PDF page numbers. This is the exact P0 bug that was fixed in May (page provenance wasn't real); confirm it's real now on a document the pipeline has never seen.
4. `extract` → `draft` → **checkpoint**: for each draft object touching `water`, `food`, `shelter`, or `power`, check against `expanded_seed/canonical/nodes/` for an existing slug covering the same concept (see the design doc's slug collision policy). Redirect to `supported_by`/extend-existing rather than duplicate.
5. `cite` → **checkpoint**: spot-check 20% of citations against the source PDF for accuracy (this is the standing TODO item "citation verification," do it here rather than deferring again).
6. `canonicalize` → review `canonicalization_log.json`; since merge/split isn't materialized yet, manually resolve anything it flagged.
7. `edges` → `bundles` → `validate` (non-strict) → fix any errors.
8. `load --dry-run` first, review `output/canonical/nodes/`, then `load --publish`.
9. Confirm the outbox worker actually processed the new `version.published` events (check `ingest_jobs`/`ingest_job_passes` or worker logs) — this is where the P0 "publish/index flow bypassed" bug used to live; it's believed fixed because `ingest load` now delegates to the same `seed_graph()` the base seed pack uses, but confirm on a real run rather than trusting the code read.

## Source 2: USDA — Complete Guide to Home Canning

Repeat steps 1-9 with:
- `--source-id src.usda.home-canning.2015`
- `--source-title "Complete Guide to Home Canning (2015 Revision)"`
- Extra attention at the draft checkpoint: this document is deep and technical (processing times, altitude adjustments, acidity tables). Make sure `structured_data` captures numeric safety parameters exactly — a canning guide is exactly the kind of high-risk content the publish gate (SAFE-001) exists for. Confirm risky objects actually route to review rather than auto-publishing.

## Source 3: OSHA 3075 — Controlling Electrical Hazards

Repeat steps 1-9 with:
- `--source-id src.osha.3075.controlling-electrical-hazards`
- `--source-title "Controlling Electrical Hazards (OSHA 3075)"`
- This document is safety-standard-shaped (hazard → control → citation format), not narrative. Use it specifically to test whether `safety_check` intent resolution and the publish gate's safety-boundary logic behave correctly on genuinely hazard-dense content — a good real-world exercise of the retrieval-intent fixes closed in May.

## Closeout

1. Re-run the eval harness: `python -m capability_commons.cli.eval run --gold eval/gold/queries.yaml --api http://127.0.0.1:8100 --out eval/reports/<date>.md`
2. Compare against `eval/reports/2026-05-14-smoke.md`. Report the delta specifically on the 5 PLAN.md canonical household queries, not just the aggregate pass rate.
3. Update `STATUS.md`'s "Content/vision gap" section — it currently says the only ingested corpus is off-mission; that sentence needs to change once this lands.
4. If the licensing decision in the design doc comes back "permissive," queue Permatil's guidebook as source 4 and update `permaculture_pack/homestead_permaculture_ingestion_blueprint.md` to drop the Mollison/Holmgren/Fukuoka references.
5. Open a follow-up research task for the architecture/owner-building domain gap rather than leaving it silently unaddressed.
