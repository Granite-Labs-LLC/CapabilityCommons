# API Gaps: Site ↔ Backend

The site's API client (`apps/site/src/lib/api.ts` and `types.ts`) was built against the original Phase 0 backend. Phases 1-4 added endpoints and response shapes the site doesn't yet consume. This document tracks what each frontend ticket needs to update.

## FE-002: Guided Ask

**Current state:** `AskTutor.tsx` calls `POST /v1/retrieve/evidence_pack` and renders raw evidence.

**Needs:**
- New client method: `askPublic(params: AskRequest): Promise<AskResponse>`
- Endpoint: `POST /v1/public/ask`
- Request type: `{ query: string; intent?: string; conversation_id?: string; context?: { housing_type?: string; climate?: string; budget?: string; experience?: string } }`
- Response type: `{ answer: string; intent: string; action_now: string[]; implementation_plan: Step[]; safety: { stop_conditions: string[]; when_to_get_help: string[] }; citations: Citation[]; related_objects: RelatedObject[]; gaps_or_uncertainties: string[]; conversation_id: string }`
- Update `AskTutor.tsx` to use the new endpoint and render structured answers

## FE-003: Search Filters

**Current state:** `SearchPanel.tsx` does client-side filtering on pre-fetched graph nodes. Does not call `POST /v1/search` with UX filters.

**Needs:**
- Update `SearchRequest` type to add: `stage?: string`, `difficulty_min?: number`, `difficulty_max?: number`, `cost_band?: string`, `risk_band?: string`, `beginner_safe?: boolean`, `housing_type?: string`, `climate?: string`, `experience?: string`
- Move from client-side filtering to server-side `POST /v1/search` with the new params
- Build filter UI components for the new params (dropdowns/toggles)

## FE-004: Action Cards & Citations

**Current state:** Object detail pages render `markdown_body` as prose. No structured answer display.

**Needs:**
- New type: `ImplementationProfile` with `smallest_viable_version`, `tools_materials`, `estimated_time`, `estimated_cost`, `success_checks`, `stop_conditions`, `common_mistakes`, `variants`, `escalation_guidance`
- Access via `structured_data.implementation_profile` on `PublicObjectResponse`
- Components: `AnswerCard`, `ImplementationPlan`, `CitationDrawer`, `ContradictionNotice`, `RelatedObjectCards`

## FE-005: Print/Offline Views

**Current state:** `print.css` exists with basic print styles.

**Needs:**
- Action-card-specific print layout (materials, safety, citations preserved)
- Implementation plan step cards in print view
- Save/download mechanism for offline bundles

## FE-006: Feedback & Analytics

**Current state:** No feedback mechanism.

**Needs:**
- New client method: `submitFeedback(params: FeedbackRequest): Promise<void>`
- Endpoint: `POST /v1/feedback` (backend endpoint also needs to be created)
- Request type: `{ answer_id?: string; run_id?: string; object_slug?: string; action: 'thumbs_up' | 'thumbs_down' | 'used_this' | 'report_issue'; comment?: string }`
- `AnswerFeedback` component with thumbs up/down, "used this", "report issue" buttons
- Analytics events: answer_viewed, answer_printed, answer_copied, answer_rated
