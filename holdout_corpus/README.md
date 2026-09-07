# Holdout Corpus — Private A/B Benchmark Sources

**Nothing in this directory is part of the public commons.** It exists to let the ingestion and retrieval pipeline be benchmarked against sources that are not licensed openly enough for `expanded_seed/` or a real `ingestion/projects/` run.

## Why this exists

VISION.md and CONTRIBUTING.md commit this project to an open-licensed, freely redistributable core corpus. Some of the best-written, most topically relevant source material for the household-resilience domains — starting with the sources `permaculture_pack/homestead_permaculture_ingestion_blueprint.md` originally named — doesn't clear that bar. Rather than either (a) ingesting them into the public corpus anyway, or (b) throwing away a chance to actually test the pipeline against strong domain content, this directory holds them **for private, internal use only**: run the pipeline against them, compare retrieval quality against the public sources in `docs/superpowers/plans/2026-09-06-resilience-corpus-ingestion.md`, and never publish the derived objects.

## Rules for anything placed in this directory

1. **Never run `ingest load --publish` against a holdout project.** Load with `--dry-run` only, or load unpublished (`draft` lifecycle) into a throwaway workspace, never `capability-commons` (the production workspace slug).
2. **Never merge a holdout object's slug or content into `expanded_seed/` or any `ingestion/projects/` output that gets published.**
3. **Never commit the source PDF itself to a public branch or a public GitHub remote** if there is any question about whether this repo (or a fork of it) is or will become public. Verify the remote's visibility before adding a binary here. If in doubt, keep the acquired PDF local-only (`.gitignore`'d) and commit only this documentation.
4. Record the exact license and source URL for anything added here — see the per-source subdirectory.
5. This is for A/B **pipeline and retrieval quality testing only** — comparing "how well does the system perform against strong permaculture content" vs. "how well does it perform against FEMA/USDA/OSHA" — not a backdoor for populating the real commons with content that doesn't meet its own licensing bar.

## What's excluded, and why

`permaculture_pack/homestead_permaculture_ingestion_blueprint.md` names Mollison, Holmgren, and Fukuoka as core sources. None of the three has a free, legal full-text PDF distribution — they are commercially sold, copyrighted books. **Do not source these, even for private/internal testing.** Acquiring a full-text copy would mean acquiring an infringing copy; that's not something to do quietly "for testing," and isn't done here. If genuine access is wanted (e.g. a personally-owned print copy scanned for private research use), that's a decision for a human to make deliberately, not something to automate or delegate.

## Current holdout sources

| Source | Status | License |
|---|---|---|
| `permatil-tropical-guidebook/` | **Documented, not yet acquired** — see its README | CC BY-NC-SA 4.0 |
