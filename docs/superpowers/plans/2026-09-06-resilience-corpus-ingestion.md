# Plan: Resilience Corpus Ingestion

Design: [2026-09-06-resilience-corpus-ingestion-design.md](../specs/2026-09-06-resilience-corpus-ingestion-design.md)

Runs three public-domain sources through the pipeline in sequence, each with a review checkpoint, so a bad run on source 1 doesn't compound into sources 2 and 3.

## Pre-flight (blocking) — all done as of 2026-09-08

- [x] Embedding backfill for the 49 (now 51) existing seed objects — done 2026-09-07, see retrieval-verification plan/design docs.
- [x] `OPENAI_API_KEY` confirmed working; outbox worker running throughout the FEMA run. Note: the ingest CLI reads the key from `os.environ`, not `.env` — export it explicitly (`OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' .env | cut -d'=' -f2-) .venv-ingest/bin/python -m capability_commons.cli.ingest ...`) before any LLM-calling pass.
- [x] `pip install -e '.[ingest]'` — **not into the main `.venv`** (Python 3.14): `polars` has no compiled runtime for 3.14 at all (confirmed via `polars-runtime-32`'s own PyPI classifiers, which list only 3.10–3.13). Created a second venv instead: `python3.13 -m venv .venv-ingest && .venv-ingest/bin/pip install -e '.[ingest]'`. Use `.venv-ingest/bin/python -m capability_commons.cli.ingest ...` for every command below.

## Source 1: FEMA — Are You Ready? — **done 2026-09-08**

1. ~~Download~~ Done — `archive.org/download/FemaEmergencyHandbook-areYouReady/FemaEmergencyHandbook-areYouReady.pdf`, 22MB, saved to `ingestion/projects/emergency-prep-fema/sources/fema-are-you-ready.pdf`.
2. ~~`ingest init`~~ Done, `--source-id src.fema.are-you-ready.2004`.
3. ~~`parse`~~ Done, after fixing a real bug: `convert_pdf_to_markdown()` never set `output_format` in `ConfigParser`'s options, and marker-pdf 1.10.2's `get_renderer()` indexes that key directly with no default (`KeyError`) — the parse pass had apparently never run against a real PDF with this marker-pdf version before. One-line fix in `cli/ingest/parse.py`. 307 segments from 204 pages. **Checkpoint passed**: spot-checked 5 segments' `page_start` against the raw PDF via `pypdfium2` — all 5 matched exactly (page 1 title, page 3 CERT intro, page 96 earthquake section, page 99 knowledge check, page 200 "Documents and Keys" appendix). Confirms the May P0 page-provenance fix holds on a document the pipeline had never seen.
4. ~~`extract`~~ Done — 303 rows from 192 sections, 0 failures. ~~`draft`~~ Done — 296/303 objects drafted after two rounds (16 failed the first pass, mostly `skill_guide requires structured_data.implementation`; retried the failures with `--skip-existing`, 9 more succeeded, 4 persistently failed the same way after 6 total LLM attempts and were left undrafted — one of them, `emergency.water-storage`, would have competed with the existing seed slug `water.safe-storage` anyway, so losing it isn't a real loss). **Checkpoint**: cross-checked drafted water/food/shelter/power slugs against `expanded_seed/canonical/nodes/` — **no exact slug collisions** (FEMA's LLM used `emergency.*`/`safety.*`/`environment.*` prefixes throughout, never the seed pack's `water.*`/`food.*`/`power.*`/`shelter.*` convention), but real *conceptual* overlap exists without collision (e.g. `emergency.water-treatment-methods` vs. seed's `water.treatment-selection`) — flagged in TODO.md as a deliberate, not-yet-done manual reconciliation task rather than something forced through automatically.
5. ~~`cite`~~ Done — 1590 citations linked across 284 drafts on the first pass (1 JSON-parse failure), 1588 after excluding 4 objects held back for insufficient citation count (see below). **Checkpoint passed**: spot-checked 6 random citations' excerpts against the raw PDF via `pypdfium2` — 5/6 matched exactly on the stated page; the 6th (`security.homeland-security-advisory-system`, cited as page 174) was off by one page (the real content was on PDF page 175 — page 174 is a 37-character section-divider stub, "4.7 Homeland Security Advisory System," with the body text flowing to the next page). A minor, documented imperfection (a section-header/page-break edge case in marker's own page attribution), not a fabricated citation — not chased further given it's 1/6 and the mechanism is understood.
6. ~~`canonicalize`~~ Done — 39 decisions, all internal to this project's own drafts (e.g. `emergency.returning-home-safely` → `emergency.returning-home`). Confirmed it has **no visibility into the seed pack at all** — this is the design doc's already-documented limitation, not a new finding, but now concretely confirmed rather than assumed.
7. ~~`edges`~~ Done — 32 edges extracted, 15 dangling (LLM hallucinated non-existent targets, mostly around a `winter-storms-extreme-cold` node referencing heat/cold concepts that were never separately drafted) — dropped. Found and fixed a related bug: 5 objects had an `id` field that disagreed with their own `slug` field, and `edges`/`validate.py` resolve identifiers differently (`id` vs. `slug`) — remapped `edges.csv` through an `id → slug` table, leaving 17 valid edges, 0 dangling. ~~`bundles`~~ Done — 66/66 generated cleanly. ~~`validate`~~ (non-strict) → fixed all errors (see step 8).
8. ~~`load --dry-run`~~ Done, iteratively, alongside fixing `validate`'s 40 initial errors: 21 `risk_band=high requires safety_boundary` (concept_note/reference_sheet content about nuclear/terrorism/tsunami/heat-stroke hazards, correctly classified high-risk by the LLM but missing the caveat field — authored real safety_boundary text for all 21, 2 of which were genuinely actionable types needing more specific content, not boilerplate) and 19 dangling-edge errors (fixed in step 7). Also held back 4 objects that never reached the 2-citation minimum for publishing (`ingestion/projects/emergency-prep-fema/needs-review/`) rather than forcing them through. ~~`load --publish`~~ Done on the clean 275: **275 objects created, 1615 evidence spans, 17 edges** (`seed_graph()`'s own report).
9. ~~Confirm the worker processed the new events~~ Done — worker drained the backlog and embedded 265/275 objects cleanly. **Found a genuinely new, not-yet-root-caused bug**: 10 of the 275 objects' `version.published` outbox events reference an `object_id`/`version_id` matching no persisted row, even though all 275 objects genuinely exist (confirmed by creation timestamp). Those 10 real, published objects have zero `content_segments` as a result — invisible to search despite existing. Stuck outbox events deleted (worker was retrying them forever); root cause not found — flagged in TODO.md.

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

## Closeout — partial (source 1 of 3 done 2026-09-08; steps below apply to that checkpoint, full closeout waits for USDA + OSHA)

1. ~~Re-run the eval harness~~ Done: `eval/reports/2026-09-08.md`, 4/11 passed.
2. Compared against `eval/reports/2026-09-07.md` (5/11, the pre-FEMA checkpoint — not the stale 2026-05-14 baseline, which was already superseded before this ingestion started). The raw count went down by one, but **not a regression**: `≥2 citations` went from 5/11 → **11/11** (every answer now has real, page-anchored evidence — the single biggest gap documented in the retrieval-verification spec is closed), and the pass-count dip is entirely explained by the already-documented gold-file/slug-naming mismatch generalizing to a growing corpus: FEMA content like `emergency.chlorination` is a genuinely good, well-cited answer to "is bleach safe for treating drinking water?", it's just not the exact slug (`water.chlorine-treatment`) `eval/gold/queries.yaml`'s `expects_any` list names. Reconciling the gold file against the real corpus is now a flagged TODO item, not silently absorbed into "the ingestion made things worse."
3. ~~Update STATUS.md's "Content/vision gap" section~~ Done — full account of the FEMA run, bugs found/fixed, and the eval delta.
4. Not addressed this round — still open, unrelated to the public-domain FEMA/USDA/OSHA sources this plan covers.
5. Not addressed this round — still open.

**Remaining for full closeout**: run USDA *Complete Guide to Home Canning* (source 2) and OSHA 3075 *Controlling Electrical Hazards* (source 3) per the sections above (same 9-step pattern, same pre-flight now already satisfied), then re-run this closeout checklist for real against all three sources combined.
