# Permatil — Tropical Permaculture Guidebook (International Edition)

**Status: documented this session, not yet downloaded.** The disk this was researched on had ~650MB free at the time (see `docs/superpowers/plans/2026-09-06-repo-hygiene-checklist.md` — flagged separately, this is a real constraint on the dev machine, not specific to this download). Don't pull the full book or even a chapter until there's comfortable headroom (several GB), since the ingestion pipeline itself (marker-pdf and friends) also needs real disk space to run against whatever lands here.

## What it is

Permatil (Permaculture Timor Lorosa'e) / Permatil Global's *Tropical Permaculture Guidebook*, the modern, actively-maintained descendant of the reference book the original `permaculture_pack` blueprint was implicitly reaching for (it cited Mollison/Holmgren/Fukuoka, but this is the closer real-world analog to the "IDEP/Permatil Reference Book" the blueprint also names — same organization, current edition). It's the direct-experience, workshop-tested, appropriate-technology counterpart to the classic (but closed-license) permaculture canon.

**License: CC BY-NC-SA 4.0** (Attribution-NonCommercial-ShareAlike), confirmed directly from permatilglobal.org this session. This is why it's here and not in `expanded_seed/` — the NC clause means derived objects can't be folded into a corpus meant for unrestricted (including commercial) reuse without a separate decision (see `docs/superpowers/specs/2026-09-06-resilience-corpus-ingestion-design.md`'s licensing decision point).

## Available chapters (confirmed this session via permatilglobal.org/individual-chapters)

Sold/distributed per-chapter rather than as direct hotlinks — access is through the site's own knowledge-bank interface, not a plain URL a script can fetch. A human needs to click through it once.

| # | Chapter | Pages | Size (web / print) | Maps to |
|---|---|---|---|---|
| 1 | Permaculture ethics and principles | 44 | 4.3MB / 8.4MB | `permaculture.*` concept notes |
| 2 | Natural patterns | 20 | 2.2MB / 5.3MB | `permaculture.patterns-in-nature` |
| 3 | Permaculture design strategies and techniques | 88 | 9.2MB / 20.1MB | `permaculture.methods-of-design`, zones/sectors |
| 4 | Urban and community permaculture | 55 | 5MB / 6.9MB | `community.*` |
| 5 | Cooperatives | 27 | 2MB / 3.5MB | `community.*` |
| 6 | Trainer's guide | 32 | 6.3MB / 8.7MB | teach-forward / facilitator structure |
| **7** | **Houses, water and energy** | 78 | 7.2MB / 13.6MB | **`water.*`, `shelter.*`, `power.*` — most direct overlap with the existing seed pack, best A/B candidate** |
| 8 | Food, health and nutrition | 44 | 2.6MB / 4.2MB | `food.*` |
| **9** | **Soils** | 64 | 4.4MB / 9.5MB | new `soil.*` domain from the blueprint |
| 10 | Family gardens | 78 | 9.5MB / 18.5MB | `food.beginner-garden-system` and new `gardens.*` |
| 11 | Seeds and propagation | 36 | 3MB / 6MB | `food.seed-starting` |
| 12 | Plant nurseries | 36 | 5.2MB / 9MB | new `gardens.*` |
| 13 | Sustainable agriculture | 64 | 5.9MB / 12MB | new `farming.*` |
| 14 | Integrated pest management | 68 | 6.1MB / 11.9MB | new `farming.*` |
| 15 | Trees | 72 | 6.5MB / 13MB | new `forests.*` |
| 16 | Bamboo | 40 | 3.2MB / 6.5MB | new `forests.*` |
| 17 | Animals | 84 | 7.3MB / 14.6MB | new `animals.*` |
| 18 | Aquaculture | 64 | 6.6MB / 11.3MB | new `aquaculture.*` |

## Recommended A/B pair for the first benchmark

**Chapter 7 (Houses, water and energy)** is the best first pick: it overlaps almost exactly with the FEMA *Are You Ready?* source recommended as the first **public** ingestion run (water storage/treatment, shelter, backup power). Running both through the pipeline and comparing citation quality, object structure, and eval-harness performance on the same gold-query cluster is a clean, controlled A/B — same domain, two different sources, one open and one not.

## To actually acquire it

1. Visit `https://permatilglobal.org/individual-chapters/` (or `/complete-guidebook/` for the full book) and go through the site's own purchase/download flow — it's free/CC-licensed content, but gated behind their interface, not a direct link.
2. Save the PDF to this directory as `ch07-houses-water-energy.pdf` (or the relevant chapter number).
3. Confirm free disk space is comfortably above the chapter's size before downloading (see the repo hygiene checklist for the current disk situation).
4. Follow `docs/superpowers/plans/2026-09-06-resilience-corpus-ingestion.md`'s pipeline steps, but load into a scratch/throwaway workspace and never `--publish` — see the rules in `holdout_corpus/README.md`.
