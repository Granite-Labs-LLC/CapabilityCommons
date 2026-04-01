# FE-001: Import Frontend Site as Submodule

**Date:** 2026-03-31
**Status:** Approved
**Ticket:** FE-001

## Goal

Bring the existing CapabilityCommonsSite into this repo as a git submodule at `apps/site`, verify it builds, and document the API gaps that subsequent Phase 3 tickets (FE-002 through FE-006) will need to address.

## Context

The frontend site already exists as a production-quality Astro 5 + React 19 application at `git@github.com:Granite-Labs-LLC/CapabilityCommonsSite.git`. It has:

- 18 Astro pages, 25+ components, 5 React islands
- Professional D3 graph explorer with force-directed clustering
- Typed API client with mock data fallback
- Full design token system (colors, typography, spacing, risk levels)
- Print styles, responsive design, accessibility
- 6 dependencies (Astro 6, React 19, D3)

Rather than rebuilding, we integrate it as a submodule to preserve git history and allow independent frontend development.

## Scope

### In Scope

1. **Add git submodule** at `apps/site` pointing to `git@github.com:Granite-Labs-LLC/CapabilityCommonsSite.git`
2. **Verify the site builds** — `npm install && npm run build` succeeds
3. **Create `apps/API_GAPS.md`** documenting what the site's API client needs for Phase 2-4 backend features
4. **Update docs** — ARCHITECTURE.md and STATUS.md to reference the submodule

### Out of Scope

- No code changes inside `apps/site`
- No API client updates (deferred to FE-002/003/004)
- No new frontend features

## API Gap Documentation

`apps/API_GAPS.md` will document these gaps between the site's current API client and the backend's current endpoints:

### FE-002: Guided Ask

The site's `AskTutor.tsx` currently calls `POST /v1/retrieve/evidence_pack`. It needs:

- New client method for `POST /v1/public/ask`
- `AskResponse` type with `answer`, `action_now`, `implementation_plan`, `safety`, `citations`, `related_objects`, `uncertainties`
- `conversation_id` support for multi-turn follow-up
- Optional intent selector and context capture (housing_type, climate, budget, experience)

### FE-003: Search Filters

The site's `SearchPanel.tsx` does client-side filtering on pre-fetched nodes. It needs:

- Server-side search via `POST /v1/search` with UX filter params: `stage`, `difficulty`, `cost_band`, `risk_band`, `beginner_safe`, `housing_type`, `climate`, `experience`
- Updated `SearchRequest` type to include these fields
- Filter UI components for the new params

### FE-004: Action Cards & Citations

The site renders raw markdown. It needs:

- `AnswerCard` component for structured answer display (direct answer + action_now)
- `ImplementationPlan` component for step cards with materials/tools
- `CitationDrawer` component for expandable citation excerpts
- `ContradictionNotice` component for gap/uncertainty display
- `RelatedObjectCards` component linking to `/explore/{slug}`
- Types for `implementation_profile` projection from `GET /v1/public/objects/{slug}`

### FE-005: Print/Offline Views

Print styles already exist (`print.css`). Needs:

- Action-card-specific print layout
- Implementation plan print view (materials, safety, citations preserved)
- Save/download mechanism for offline use

### FE-006: Feedback & Analytics

No feedback mechanism exists. Needs:

- `POST /v1/feedback` client method (thumbs up/down, "used this", "report issue")
- Analytics event types (answer viewed, printed, copied, rated)
- `AnswerFeedback` component tied to retrieval run or answer IDs

## Doc Updates

### ARCHITECTURE.md

Update section 6 ("Frontend: CapabilityCommonsSite") to note:

- Site is now integrated as a git submodule at `apps/site`
- Contributors must run `git submodule update --init` after cloning
- Frontend development happens in the submodule (can push independently)

### STATUS.md

Update the frontend section to note:

- Site integrated as submodule (no longer a separate deployment concern for this repo)
- API gap documentation exists at `apps/API_GAPS.md`

## Success Criteria

1. `git submodule status` shows the site at `apps/site`
2. `cd apps/site && npm install && npm run build` succeeds
3. `apps/API_GAPS.md` exists with documented gaps for FE-002 through FE-006
4. ARCHITECTURE.md and STATUS.md reference the submodule
