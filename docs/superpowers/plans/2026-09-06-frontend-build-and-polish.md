# Plan: Frontend Build Performance & Production Polish

Combined spec + plan (small enough not to need a separate design doc).

## 1. `astro build` taking 10+ minutes against a live backend

**Root cause (per `docs/superpowers/plans/2026-05-14-followups.md`, not yet independently re-verified):** `src/pages/domains/[domain].astro` calls `listPublicObjectsByDomain(domain)` per domain (7 domains). The module-scope cache (`getCachedGraphData` / `_cachedGraph`) in `src/lib/api.ts` doesn't survive Astro spinning a fresh module instance per page during static generation, so each domain re-fetches from scratch (~16s × 7+ pages).

**Plan:**
1. Reproduce first: time a real `astro build` against a live local backend before changing anything, so there's a before/after number.
2. Fix by threading the fetched data through `getStaticPaths()`'s `props` instead of relying on module-scope memoization — this is the idiomatic Astro fix for exactly this failure mode (SSG pages are isolated, `getStaticPaths` runs once and can pass data to every page it generates).
3. Apply the identical fix to `src/pages/print/[slug].astro`, which the followups doc flags as having the same problem (its `getStaticPaths` pulls every `listPublicObjects()` entry).
4. Re-time the build; target: build time should stop scaling with domain/object count in a way that makes it unusable once the corpus grows past today's 49-175 objects.

## 2. `PUBLIC_USE_MOCK` env-gating

**Problem:** `src/lib/api.ts`'s mock-data fallback is unconditional — if the real backend is unreachable or unhealthy, the site silently serves stale mock data instead of failing visibly. Fine for local dev, dangerous in production (an operator could believe the site is healthy when it's actually serving fake content).

**Plan:**
1. Add a `PUBLIC_USE_MOCK` env var (default `false` in `.env.production`/`.env.staging`, default `true` or unset-tolerant in local dev).
2. When `false` and the backend call fails, surface a real error state in the UI rather than falling back to mock data.
3. Test: with the flag off, a simulated fetch failure should render an error state, not mock content.

## 3. PWA update-available toast

**Problem:** the service worker registers and can report a `waiting` state (an update is downloaded and ready), but the UI never surfaces it — users on an old cached version have no way to know a refresh is available.

**Plan:**
1. Listen for the service worker's `waiting` event.
2. Render a small dismissible toast ("Update available — refresh to get the latest") that triggers `skipWaiting()` + reload on click.
3. Respect `prefers-reduced-motion` for the toast's entrance.

## 4. Verification items (no code, just confirming things work)

- [ ] Bundle rendering — verify six-part bundles display correctly for objects that have them (STATUS.md marks bundles "Complete" but this hasn't been re-checked against a live backend recently)
- [ ] Graph explorer — verify the D3 visualization renders correctly with the full current graph, not just the original 49-object seed graph
- [ ] End-to-end smoke test — re-run the same manual pass documented in the 2026-05-14 followups doc after the corpus-ingestion plan lands, since new content changes both data volume and shape
