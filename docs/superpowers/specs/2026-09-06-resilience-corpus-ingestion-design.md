# Design: Resilience Corpus Ingestion

Status: proposed
Owner: unassigned
Depends on: [2026-09-06-retrieval-verification-backfill-design.md](2026-09-06-retrieval-verification-backfill-design.md) (embedding backfill must land first or be run alongside)

## Problem

The ingestion pipeline has run exactly once end-to-end, against `ingestion/projects/ggg-2026-03`, a finance/geopolitics newsletter. VISION.md's corpus domains — water, food, shelter, power, repair, gardening, sanitation, epistemics — have zero pipeline-ingested content. The 49 hand-authored seed objects cover those domains but were written by hand, not extracted from a source with citations, which is the entire point of the pipeline. The 2026-05-14 eval run scored 3/11 against the live system almost entirely because the corpus it can retrieve from is off-mission.

This spec picks the next source(s) to run through the pipeline and the constraints that pick has to satisfy.

## Constraint: the corpus has to actually be open

VISION.md and `docs/context/INIT.md` both state "open license for the core corpus" as a design requirement. CONTRIBUTING.md goes further: "your work may be freely used, adapted, and redistributed as part of the commons."

`permaculture_pack/homestead_permaculture_ingestion_blueprint.md` — a design document already in this repo — names Mollison, Holmgren, and Fukuoka as core sources. All three are commercially copyrighted books with no open license. Ingesting them would put copyrighted excerpts into a corpus the project has committed to redistributing freely. **This blueprint cannot be executed as written without a licensing decision the pipeline itself can't make.** It is not this spec's job to silently swap in different sources and call the blueprint done — see the licensing decision point below.

## Candidate sources (verified this session, not from training-data memory alone)

| Source | Domains covered | License | Format | Verdict |
|---|---|---|---|---|
| FEMA *Are You Ready? An In-Depth Guide to Citizen Preparedness* (P-2064 / IS-22) | water, food, shelter, power, general emergency planning | Public domain (17 U.S.C. §105 — US government work) | Single combined PDF (archive.org: `FemaEmergencyHandbook-areYouReady`; stable `.mil` mirror also found) | **Recommended — run first** |
| USDA *Complete Guide to Home Canning*, 2015 revision (Ag Info Bulletin No. 539) | food (preservation, deep) | Public domain (USDA) | Single PDF, 193pp, stable at archive.org and healthycanning.com | **Recommended — run second**, deepens `food` beyond FEMA's overview level |
| OSHA 3075, *Controlling Electrical Hazards* | power/electrical safety | Public domain (OSHA) | Single PDF, 71pp, osha.gov | **Recommended — run third**, exercises `safety_check` intent and the publish gate on hazard content; addresses the "electrical work" domain the user asked about, though it's a safety standard, not a wiring how-to |
| DOE *Energy Saver Guide* / *Consumer Guide to Home Energy Assessments* | shelter (weatherization, building envelope) | Public domain (DOE) | PDF, energy.gov | Candidate for a fourth run; overlaps somewhat with existing `shelter.weatherization-audit` seed object — use to enrich, not replace |
| Permatil *Tropical Permaculture Guidebook* (International Edition) | gardening, soil, water, appropriate technology — matches `permaculture_pack`'s intended scope closely | **CC BY-NC-SA 4.0** | PDF, ~87–196MB, chapters also available individually at permatilglobal.org | **Gated — see licensing decision below.** Far better than Mollison/Holmgren/Fukuoka (which have no open license at all) but the NonCommercial clause is more restrictive than a plain "open license"; several open-source/open-content definitions (e.g. the Open Definition) explicitly exclude NC-restricted works from counting as "open." |
| Peace Corps ICE technical manuals (water/sanitation, appropriate technology, construction) | water, sanitation, appropriate technology | Public domain (US government work), same as FEMA/USDA | **Fragmented** — Peace Corps does not archive most ICE titles as clean single PDFs; usable copies exist scattered across ERIC (`files.eric.ed.gov`) and archive.org, title by title | Good backfill material later; not a clean first pick because sourcing takes more manual work per document |
| Architecture / owner-building (explicitly asked about) | shelter (construction, not just envelope) | — | — | **No strong open candidate found.** HUD publishes program/administrative material on self-help housing, not construction technique. This is a real, unresolved sourcing gap — see Open Questions. |

### Licensing decision needed from the maintainer

Two choices, not decided by this spec:

1. **Strict**: only ingest public-domain or CC-BY/CC-BY-SA sources with no NC restriction. Permatil's guidebook does not qualify; the gardening/permaculture domain waits for a compliant source (Appropedia.org, CC-BY-SA, is a plausible fallback — wiki content, would need PDF export and heavier review for quality/consistency).
2. **Permissive**: accept CC BY-NC-SA sources into the corpus, understanding that the commons cannot then guarantee unrestricted commercial reuse of every object's source excerpt. If chosen, Permatil's guidebook is a strong fit and should **replace** the Mollison/Holmgren/Fukuoka references in `permaculture_pack/homestead_permaculture_ingestion_blueprint.md` (update that document once decided, don't leave it pointing at copyrighted texts).

This spec proceeds on FEMA/USDA/OSHA regardless of which way that decision goes, since all three are unconditionally public domain.

## Slug collision policy

25 seed objects already exist (`water.safe-storage`, `water.treatment-selection`, `food.pantry-design`, `food.pantry-rotation`, `food.safe-preservation-basics`, `power.backup-power-plan`, `shelter.weatherization-audit`, etc. — see `expanded_seed/canonical/nodes/`). The eval gold set (`eval/gold/queries.yaml`) already expects several of these exact slugs to be the right answer.

New ingestion runs must **not** create competing slugs for the same concept (e.g. a new `water.emergency-water-storage` next to the existing `water.safe-storage`). During the `cite`/`canonicalize` review step, cross-check extracted concepts against the existing seed slug list and either:
- attach new evidence/citations to the existing object via `supported_by` edges, or
- extend the existing object's content if the source materially adds to it, or
- create a genuinely new slug only for concepts the seed pack doesn't cover.

The current `canonicalize` pass only *routes* files (`_merged/`/`_split/` + a log) rather than materializing merges — this is a known open gap (see TODO.md). Until it's fixed, this cross-check has to happen manually during human review, not automatically.

## Dependency: embedding backfill

Hypothesis worth confirming before or during this work (see the paired retrieval-verification spec): the 49 seed objects were likely loaded before `OPENAI_API_KEY` embedding indexing was wired in, or before the outbox worker ever processed their `version.published` events with a valid key. If so, they may have `NULL` vector embeddings today. In `search_hybrid`'s reciprocal-rank-fusion, an object with no vector candidate at all is structurally disadvantaged against newly-ingested objects that do have embeddings — independent of actual relevance. If this is confirmed, **run the embedding backfill before drawing conclusions from a post-ingestion eval run**, or a good FEMA-sourced water object could still lose to noise for reasons that have nothing to do with content quality.

## Success criteria

- All five PLAN.md "Days 15-45" canonical queries in `eval/gold/queries.yaml` (drinking water, starter solar, renter-safe food, rain barrel, off-grid refrigeration) return real, on-topic results instead of GGG finance content.
- Eval harness score materially improves on the water/food/power queries specifically (today: 0/5 on that cluster).
- No new object duplicates an existing seed slug's concept.
- At least one object per ingested source has ≥2 citations with page-anchored provenance (this is the actual test of the P0 parse/cite fixes closed in May, not just a content-population exercise).

## Open questions

- Does the ingest CLI support multiple source documents per project, or does each source need its own `ingest init` project? Checked this session: `ingest init` takes exactly one `--source`; the manifest schema (`project.py`) stores `sources` as a list, but there's no `add-source` command exposed. Treat each source as its own project until proven otherwise.
- Architecture/owner-building has no verified open source yet. Worth a dedicated follow-up research spike rather than forcing a weak pick into this run.
- Peace Corps ICE material is real and public domain but fragmented across ERIC/archive.org with no clean catalog; worth revisiting once the pipeline has proven itself on FEMA/USDA/OSHA.
