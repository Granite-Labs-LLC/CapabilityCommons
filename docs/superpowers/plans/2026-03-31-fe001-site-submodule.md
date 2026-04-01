# FE-001: Import Frontend Site as Submodule — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing CapabilityCommonsSite as a git submodule at `apps/site`, verify it builds, and document API gaps for subsequent tickets.

**Architecture:** Add a git submodule reference, verify the frontend builds independently, create an API gap document for FE-002 through FE-006, and update project docs to reflect the new structure.

**Tech Stack:** Git submodules, Node.js 22+, npm, Astro 6

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/site` | Create (submodule) | Git submodule pointing to CapabilityCommonsSite |
| `.gitmodules` | Auto-created by git | Submodule configuration |
| `apps/API_GAPS.md` | Create | Documents what the site's API client needs for Phase 2-4 features |
| `docs/ARCHITECTURE.md` | Modify | Update section 6 to reference submodule |
| `STATUS.md` | Modify | Update frontend section to note submodule integration |

---

### Task 1: Add the git submodule

**Files:**
- Create: `apps/site` (submodule)
- Auto-created: `.gitmodules`

- [ ] **Step 1: Create the apps directory and add the submodule**

```bash
mkdir -p apps
git submodule add git@github.com:Granite-Labs-LLC/CapabilityCommonsSite.git apps/site
```

Expected output: `Cloning into '/Users/nuggylover1210/Projects/CapabilityCommons/apps/site'...`

- [ ] **Step 2: Verify the submodule is registered**

```bash
git submodule status
```

Expected: A line showing a commit hash and `apps/site`

- [ ] **Step 3: Verify `.gitmodules` was created**

```bash
cat .gitmodules
```

Expected:
```
[submodule "apps/site"]
	path = apps/site
	url = git@github.com:Granite-Labs-LLC/CapabilityCommonsSite.git
```

- [ ] **Step 4: Commit**

```bash
git add .gitmodules apps/site
git commit -m "feat: add CapabilityCommonsSite as submodule at apps/site (FE-001)"
```

---

### Task 2: Verify the site builds

**Files:**
- None modified — read-only verification

- [ ] **Step 1: Install dependencies**

```bash
cd apps/site && npm install
```

Expected: `added XXX packages` with no errors

- [ ] **Step 2: Run the build**

```bash
cd apps/site && npm run build
```

Expected: Astro build completes successfully, output in `apps/site/dist/`. The build may show warnings about missing backend (the site has mock data fallback) — that's fine. It must not error.

- [ ] **Step 3: Verify the dist output exists**

```bash
ls apps/site/dist/index.html
```

Expected: File exists

- [ ] **Step 4: Return to repo root**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons
```

No commit needed — this was a verification step. The `node_modules/` and `dist/` inside the submodule are gitignored by the submodule's own `.gitignore`.

---

### Task 3: Create API_GAPS.md

**Files:**
- Create: `apps/API_GAPS.md`

- [ ] **Step 1: Create the API gap document**

Create `apps/API_GAPS.md` with the following content:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add apps/API_GAPS.md
git commit -m "docs: add API gap documentation for FE-002 through FE-006 (FE-001)"
```

---

### Task 4: Update ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md` (section 6, around line 356)

- [ ] **Step 1: Find and update section 6 heading**

Find the line:
```markdown
## 6. Frontend: CapabilityCommonsSite
```

Replace the section intro (the text between the heading and `### Project Layout`) with:

```markdown
## 6. Frontend: CapabilityCommonsSite

The frontend is integrated as a git submodule at `apps/site`, pointing to `git@github.com:Granite-Labs-LLC/CapabilityCommonsSite.git`.

**Setup after cloning:**
```bash
git submodule update --init
cd apps/site && npm install
```

**Development:**
```bash
cd apps/site && npm run dev    # Astro dev server on :4321
```

**Build:**
```bash
cd apps/site && npm run build  # Static output to apps/site/dist/
```

The site is an Astro 6 static site with React 19 islands for interactivity (graph explorer, search, AI tutor). It consumes the FastAPI backend via a typed API client with mock data fallback for offline development.

**API gap tracking:** See `apps/API_GAPS.md` for what the site's API client needs to support Phase 2-4 backend features.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: update ARCHITECTURE.md to reference apps/site submodule (FE-001)"
```

---

### Task 5: Update STATUS.md

**Files:**
- Modify: `STATUS.md` (frontend section, around line 166)

- [ ] **Step 1: Update the frontend section heading and intro**

Find:
```markdown
### Frontend (CapabilityCommonsSite) — Functional
```

Replace with:
```markdown
### Frontend (CapabilityCommonsSite) — Integrated
```

- [ ] **Step 2: Add submodule note after the frontend features table**

Find the line:
```markdown
**Pages:** 14 Astro pages (including /status), 25+ components, 5 React islands.
```

Replace with:
```markdown
**Pages:** 18 Astro pages, 25+ components, 5 React islands.

**Integration:** Added as git submodule at `apps/site`. API gap documentation at `apps/API_GAPS.md` tracks what the site needs to support Phase 2-4 backend features (guided ask, UX search filters, action cards, feedback).
```

- [ ] **Step 3: Commit**

```bash
git add STATUS.md
git commit -m "docs: update STATUS.md frontend section for submodule integration (FE-001)"
```

---

### Task 6: Final verification

- [ ] **Step 1: Verify submodule status**

```bash
git submodule status
```

Expected: Shows commit hash and `apps/site`

- [ ] **Step 2: Verify API_GAPS.md exists**

```bash
ls apps/API_GAPS.md
```

Expected: File exists

- [ ] **Step 3: Verify recent commits**

```bash
git log --oneline -5
```

Expected: 4 commits for FE-001 (submodule add, API gaps doc, ARCHITECTURE update, STATUS update)

- [ ] **Step 4: Run backend tests to confirm nothing broke**

```bash
.venv/bin/python -m pytest tests/ --ignore=tests/test_integration.py -q
```

Expected: All tests pass (267+), no regressions
