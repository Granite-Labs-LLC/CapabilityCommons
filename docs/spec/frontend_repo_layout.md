# Frontend Repository Layout

## Location

The public site lives at `apps/site/` inside the CapabilityCommons monorepo. This keeps API contracts and frontend in lockstep.

## Directory Structure

```
apps/site/
  package.json
  astro.config.mjs
  tsconfig.json
  src/
    pages/
      index.astro          # Landing page with problem starters
      ask.astro            # Guided ask experience
      search.astro         # Problem-first search
      explore/
        [slug].astro       # Object detail page
    components/
      AskComposer.tsx      # Chat entry + context panel
      ContextPanel.tsx     # Housing, climate, budget, experience
      IntentSelector.tsx   # Optional intent picker
      ProblemStarters.tsx  # Starter prompts on first load
      SearchFilters.tsx    # UX-friendly filter controls
      SearchResults.tsx    # Search result list
      ResultCard.tsx       # Individual search result
      AnswerCard.tsx       # Direct answer + action_now
      ImplementationPlan.tsx # Step-by-step action cards
      CitationDrawer.tsx   # Expandable citation excerpts
      ContradictionNotice.tsx # Contradiction/gap warnings
      RelatedObjectCards.tsx  # Related objects sidebar
      AnswerFeedback.tsx   # Thumbs up/down + field report
      PrintView.tsx        # Print/offline-friendly layout
    lib/
      api.ts              # API client for /v1/public/*
      types.ts            # TypeScript types matching API contracts
      analytics.ts        # Feedback and usage events
    styles/
      tokens.css          # Design tokens
      print.css           # Print-specific styles
  public/
    favicon.svg
```

## Ownership Boundaries

| Area | Owner | Notes |
|------|-------|-------|
| `apps/site/` | Frontend | Full ownership of UI, components, styles |
| `src/capability_commons/api/routes/public*.py` | Backend | API contract — changes need frontend coordination |
| `src/capability_commons/schemas/retrieval.py` | Backend | Response shapes — changes need frontend coordination |
| `docs/spec/` | Shared | Approved contracts — changes need both teams |

## Build and Deploy

- **Framework:** Astro with React islands for interactive components
- **Build:** `npm run build` produces static + SSR output
- **Dev:** `npm run dev` with `API_BASE_URL` env var pointing to local backend
- **CI:** Build check runs on every PR touching `apps/site/`
