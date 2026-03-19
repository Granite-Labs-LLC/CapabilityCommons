# Capability Commons — Website Scaffold Plan

> A public learning platform that consumes the FastAPI/Postgres backend and makes the knowledge graph navigable, searchable, and actionable for ordinary people.

**Date:** 2026-03-12
**Status:** Design — ready for implementation
**Depends on:** FastAPI v1 API (operational), 25-node seed graph (loaded)

---

## 1. Architectural context

The backend already exists as a FastAPI modular monolith with:

- 19 Postgres tables (context objects, versions, facets, edges, evidence, reviews, retrieval runs)
- Public read API: `/v1/public/objects/{slug}`, `/v1/public/modules/{slug}`, `/v1/public/paths/{slug}`, `/v1/public/objects/{slug}/bundle`
- Search API: `POST /v1/search` (hybrid FTS + vector)
- Retrieval planner: `POST /v1/retrieve/evidence_pack` (intent-specific, facet-filtered, evidence-grounded)
- Graph traversal via relational adapter (neighbors, prerequisites, membership)
- 25 seeded knowledge objects across 7 domains with 50 prerequisite edges and 27 navigation edges

The website's job is to make this substrate **legible, navigable, and actionable** for non-technical users. It is a frontend application consuming the existing API, not a second data store.

---

## 2. Tech stack

### Recommended: Astro 5 + React islands

**Why Astro:**

- Static-first with server-side rendering — fast page loads, good SEO for public content
- Island architecture — heavy interactivity (graph explorer, search, AI tutor) ships as React islands; static content pages ship zero JS
- Content is structured and API-driven, not file-based MDX — Astro's SSR mode fetches from the FastAPI backend at build or request time
- Consistent with the existing site infrastructure (personal site, GAMUT site are both Astro)
- Native support for view transitions, prefetching, and progressive enhancement

**Supporting stack:**

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | Astro 5 (SSR mode) | Pages, routing, data fetching |
| Interactive islands | React 19 | Graph explorer, search panel, AI tutor, filters |
| Graph visualization | D3.js (force-directed) | Knowledge graph explorer |
| Styling | CSS custom properties + Tailwind utilities | Design tokens, responsive layout |
| Search UX | React component consuming `/v1/search` | Real-time search with facet filters |
| AI tutor | React component consuming `/v1/retrieve/evidence_pack` | Intent-based Q&A grounded in the graph |
| Build/deploy | Astro SSR adapter (Node.js or Cloudflare) | ISR for public content, SSR for dynamic pages |
| API client | Shared TypeScript fetch wrapper | Typed API consumption with error handling |

### Alternative considered: Next.js

Next.js would also work and provides stronger SSR primitives, but adds more client-side JS by default and doesn't match the existing deployment pattern. Astro's island model is a better fit for a project where most pages are public content with selective interactivity.

---

## 3. Page map and routing

### Public pages (no auth)

| Route | Page | Data source | Interactivity |
|-------|------|------------|---------------|
| `/` | Landing / doctrine | Static + stats from API | Minimal — links, entry points |
| `/explore` | Graph explorer | `/v1/public/objects/*` + edges API | Full — D3 force graph, zoom, filter, click-through |
| `/explore/{slug}` | Knowledge object detail | `/v1/public/objects/{slug}` | Medium — prereq tree, next steps, facet badges |
| `/explore/{slug}/bundle` | Six-part module bundle | `/v1/public/objects/{slug}/bundle` | Tabs/accordion for hook, primer, guide, reference, worksheet, teach-forward |
| `/domains` | Domain browser | Aggregated from objects by domain facet | Grid navigation by civilizational function |
| `/domains/{domain}` | Single domain page | Objects filtered by domain | List + dependency graph |
| `/paths` | Learning path index | All `learning_path` objects | Cards with description, duration, difficulty |
| `/paths/{slug}` | Learning path detail | `/v1/public/paths/{slug}` | Ordered step view with progress indicators |
| `/search` | Search | `POST /v1/search` | Full — query input, facet sidebar, result list |
| `/ask` | AI tutor | `POST /v1/retrieve/evidence_pack` | Full — conversational Q&A, intent selection, citations |
| `/syllabus` | 12-week syllabus overview | Static structure, linked to modules | Minimal — links to week pages |
| `/syllabus/{week}` | Single week detail | Module object for that week | Medium — objectives, lab, deliverables |
| `/rings` | Concentric ring navigator | Objects grouped by ring/stage | Interactive concentric visualization |
| `/about` | About / doctrine | Static | None |
| `/glossary` | Zero-jargon glossary | Aggregated from object `structured_data` | Search/filter |
| `/offline` | Offline kits and printables | Static export links + PDF downloads | None |

### Contributor pages (API key auth)

| Route | Page | Purpose |
|-------|------|---------|
| `/contribute` | Contribution landing | Explain how to submit field reports, adaptations, corrections |
| `/contribute/field-report` | Field report form | Submit observations, failures, adaptations |
| `/contribute/adaptation` | Local adaptation form | Submit region/context-specific variants |

### Admin/editorial pages (future, API key auth)

| Route | Purpose |
|-------|---------|
| `/admin/objects` | CRUD for knowledge objects |
| `/admin/reviews` | Review queue |
| `/admin/contradictions` | Contradiction triage |

---

## 4. Component architecture

### Layout components

```
layouts/
  BaseLayout.astro          — html, head, global nav, footer
  ContentLayout.astro       — base + sidebar prereqs + breadcrumbs
  ExplorerLayout.astro      — base + full-width for graph explorer
```

### Page sections (Astro, static)

```
components/
  sections/
    HeroLanding.astro       — thesis, doctrine summary, entry points
    DomainGrid.astro        — 5-layer domain grid (foundation → advanced)
    RingNavigator.astro     — concentric ring entry visualization
    SyllabusTimeline.astro  — 12-week visual timeline
    ObjectCard.astro        — card for a single knowledge object
    PathCard.astro          — card for a learning path
    StatsStrip.astro        — 25 objects, 50 edges, 7 domains, etc.
    DoctrineBlock.astro     — six rules rendered as a grid
    StatusBadge.astro       — lifecycle state, evidence level, risk band
    FacetPills.astro        — context applicability (renter, rural, low-cost, etc.)
    PrerequisiteTree.astro  — visual prerequisite chain
    NextSteps.astro         — "what to learn next" links
    CitationList.astro      — evidence sources for an object
    ContradictionBanner.astro — warning if unresolved contradictions
```

### Interactive islands (React)

```
islands/
  GraphExplorer.tsx         — D3 force-directed graph of knowledge objects
  SearchPanel.tsx           — search input + facet sidebar + results
  AskTutor.tsx              — AI Q&A grounded in retrieval planner
  BundleViewer.tsx          — tabbed view of six-part module bundle
  FilterBar.tsx             — domain, stage, difficulty, cost, risk filters
  ProgressTracker.tsx       — local-storage-based competence tracking
  RingExplorer.tsx          — interactive concentric ring visualization
```

### Shared utilities

```
lib/
  api.ts                    — typed fetch wrapper for the FastAPI backend
  types.ts                  — TypeScript interfaces mirroring Pydantic schemas
  graph.ts                  — graph layout helpers for D3
  filters.ts                — facet filter logic
  offline.ts                — service worker registration, cache strategies
```

---

## 5. Data flow

### Static content pages (SSR at build or on-demand)

```
Astro page
  → fetch /v1/public/objects/{slug} at build/request time
  → render HTML server-side
  → hydrate React islands only where needed
```

### Interactive pages (client-side)

```
React island
  → user types query or clicks graph node
  → fetch /v1/search or /v1/retrieve/evidence_pack
  → render results in real-time
  → link back to static object pages
```

### API client shape

```typescript
interface ApiClient {
  getPublicObject(slug: string): Promise<PublicObjectResponse>;
  getPublicBundle(slug: string): Promise<PublicBundleResponse>;
  getPublicPath(slug: string): Promise<PublicObjectResponse>;
  search(params: SearchRequest): Promise<SearchResponse>;
  retrieveEvidencePack(params: RetrievalRequest): Promise<EvidencePack>;
  getEdges(params: EdgeQuery): Promise<Edge[]>;
}
```

### TypeScript types (mirroring Pydantic schemas)

```typescript
interface PublicObjectResponse {
  slug: string;
  title: string;
  type: string;
  summary_short: string | null;
  plain_language: string;
  markdown_body: string;
  structured_data: Record<string, any>;
  facets: Record<string, string[]>;
  entities: EntityRef[];
  citations: CitationSnippet[];
  review_summary: Record<string, number>;
  contradiction_summary: Record<string, number>;
  members: MemberRef[];
}

interface SearchHit {
  object_id: string;
  version_id: string;
  slug: string;
  title: string;
  type: string;
  plain_language: string;
  score: number;
  facets: Record<string, string[]>;
}

interface EvidencePack {
  run_id: string;
  intent: string;
  answer_summary: string;
  recommended_objects: RecommendedObject[];
  citations: Citation[];
  contradictions: any[];
  gaps: string[];
}
```

---

## 6. Design system

### Principles

1. **Readable by default** — large body text, high contrast, no decorative noise
2. **Dignified tone** — not gamified, not corporate, not survivalist-aesthetic
3. **Layered information** — plain language first, technical detail expandable
4. **Context-visible** — facet pills (renter, rural, low-cost) always visible on content
5. **Trust-signaling** — lifecycle badges, evidence levels, review dates prominent
6. **Printable** — content pages should print cleanly with `@media print`

### Design tokens

```css
:root {
  /* Typography */
  --font-body: 'Source Serif 4', Georgia, serif;
  --font-ui: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Scale */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1.0625rem;
  --text-lg: 1.25rem;
  --text-xl: 1.5rem;
  --text-2xl: 2rem;
  --text-3xl: 2.5rem;

  /* Colors — warm, serious, high-contrast */
  --color-ink: #1a1a1a;
  --color-body: #333;
  --color-muted: #666;
  --color-subtle: #999;
  --color-line: #e0dcd4;
  --color-surface: #faf8f5;
  --color-card: #ffffff;
  --color-accent: #2c5f2d;        /* forest green — growth, practical */
  --color-accent-light: #e8f0e8;
  --color-warning: #b8860b;
  --color-danger: #c0392b;

  /* Status colors */
  --color-draft: #999;
  --color-reviewed: #2c5f2d;
  --color-verified: #1a6b3c;
  --color-deprecated: #b8860b;

  /* Risk band colors */
  --color-risk-low: #2c5f2d;
  --color-risk-moderate: #b8860b;
  --color-risk-high: #c0392b;
  --color-risk-expert: #8b0000;

  /* Spacing */
  --sp-1: 0.25rem;
  --sp-2: 0.5rem;
  --sp-3: 0.75rem;
  --sp-4: 1rem;
  --sp-6: 1.5rem;
  --sp-8: 2rem;
  --sp-12: 3rem;
  --sp-16: 4rem;
  --sp-24: 6rem;

  /* Layout */
  --content-width: 42rem;
  --page-width: 72rem;
  --sidebar-width: 16rem;

  /* Elevation */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.06);
  --shadow-md: 0 2px 8px rgba(0,0,0,0.08);
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

### Badge system

Every knowledge object displays:

| Badge | Source | Display |
|-------|--------|---------|
| **Type** | `context_object.type` | `skill`, `concept`, `project` |
| **Stage** | `version.stage` | `foundation`, `household`, `productive`, `community`, `advanced` |
| **Difficulty** | `version.difficulty` | 1–5 dots or bars |
| **Cost** | `version.cost_band` | `free`, `low`, `medium`, `high` |
| **Risk** | `version.risk_band` | colored badge: green/amber/red |
| **Status** | `context_object.lifecycle_state` | `draft`, `reviewed`, `verified` |
| **Evidence** | inferred from evidence + reviews | `compiled`, `field-tested`, `replicated` |
| **Beginner safe** | `version.beginner_safe` | green checkmark if true |
| **Teach-forward** | `version.teach_forward_ready` | badge if ready |

### Facet pills

Context applicability rendered as inline pills:

```
[renter] [homeowner] [urban] [rural] [low-budget] [cold climate]
```

These come from `context_object_facets` and are always visible on object cards and detail pages.

---

## 7. Key page designs

### 7.1 Landing page (`/`)

**Purpose:** Establish thesis, provide entry points, signal seriousness.

**Sections:**

1. **Hero** — "Practical knowledge is trapped. We're building the infrastructure to free it." One-paragraph thesis. Two CTAs: "Explore the Graph" and "Start a Learning Path."
2. **Doctrine strip** — six rules as a horizontal grid with icons
3. **Stats strip** — "25 capabilities · 7 domains · 50 prerequisite edges · 12-week syllabus"
4. **Three graphs explained** — concept / skill / deployment with examples
5. **Domain grid** — five layers as cards, clickable to `/domains/{domain}`
6. **Entry points** — "Start by ring" (link to `/rings`), "Start by domain" (link to `/domains`), "Start by search" (link to `/search`), "Ask a question" (link to `/ask`)
7. **About strip** — brief project context, link to `/about`

### 7.2 Graph explorer (`/explore`)

**Purpose:** Interactive visualization of the full knowledge graph.

**Layout:** Full-width canvas with sidebar filter panel.

**Components:**

- **D3 force-directed graph** — nodes colored by type (concept=blue, skill=green, project=amber), sized by connection count, clustered by domain
- **Filter sidebar** — filter by domain, stage, type, risk band, cost band
- **Click behavior** — click node → sidebar shows object summary, plain language, facets, prereqs, next steps; double-click → navigate to `/explore/{slug}`
- **Edge rendering** — prerequisite edges as arrows, navigation edges as dashed lines
- **Search integration** — search box above graph highlights matching nodes
- **Zoom controls** — semantic zoom: zoomed out = domain clusters, zoomed in = individual nodes with labels

### 7.3 Object detail (`/explore/{slug}`)

**Purpose:** Render a single knowledge object with full context.

**Sections:**

1. **Header** — title, type badge, stage badge, difficulty, cost, risk
2. **Plain language** — the `plain_language` field, always first
3. **Summary** — `summary_short` or `summary_medium`
4. **Context applicability** — facet pills
5. **Prerequisites** — visual tree of required objects with links
6. **Content body** — rendered `markdown_body`
7. **Structured payload** — type-specific data rendered appropriately:
   - Skill: performance statement, tools, materials, steps, success criteria, failure modes, safety boundary
   - Project: goal, deliverables, acceptance criteria, time box, budget
   - Concept: definition, key questions, misconceptions, formulas
8. **What's next** — navigation edges as cards
9. **Evidence & citations** — linked evidence sources with trust tier badges
10. **Review status** — review summary, contradiction banner if any
11. **Teach-forward card** — if `teach_forward_ready`, show the 3-min and 10-min outlines
12. **Sidebar** — domain breadcrumb, related objects, printable link

### 7.4 Search (`/search`)

**Purpose:** Plain-language search with context-aware filtering.

**Layout:** Two-column — filter sidebar + results.

**Components:**

- **Search input** — prominent, placeholder: "What do you need to know how to do?"
- **Filter sidebar:**
  - Domain: checkboxes for each domain
  - Stage: foundation → advanced
  - Type: concept / skill / project
  - Context: renter, homeowner, urban, rural, off-grid
  - Budget: free, low, medium, high
  - Difficulty: 1–5
  - Beginner safe: toggle
- **Results list** — cards with title, type badge, plain language, facet pills, score indicator
- **Empty state** — "Try: 'How do I keep my house warm during an outage?' or 'What tools do I need for basic repair?'"

### 7.5 AI tutor (`/ask`)

**Purpose:** Retrieval-grounded Q&A that uses the planner's intent system.

**Layout:** Chat-style interface with citations sidebar.

**Components:**

- **Query input** — "Ask about any practical capability"
- **Intent selector** — optional, defaults to auto-detect. Options: "How to do something", "What to learn next", "Why does this matter?", "Compare options", "Adapt for my situation", "Debug a problem", "How to teach this", "What changed?", "Safety check"
- **Context panel** — set your profile: housing type, climate, budget, experience level
- **Response rendering** — answer summary + recommended objects as linked cards + citations with excerpts + contradiction warnings + gaps identified
- **Follow-up** — "Ask a follow-up" input below the response

### 7.6 Ring navigator (`/rings`)

**Purpose:** Visual entry by concentric rings.

**Layout:** Concentric circles or horizontal swim lanes.

**Design:**

- Ring 1 (innermost): Stay functional — 7 capabilities
- Ring 2: Repair and maintain
- Ring 3: Produce
- Ring 4: Coordinate
- Ring 5 (outermost): Steward and transmit

Each ring shows its capabilities as nodes. Clicking a node navigates to `/explore/{slug}`. Current ring framing question displayed prominently ("How do I keep myself and my household stable?").

---

## 8. Graph visualization approach

### D3 force-directed graph

The graph explorer is the signature interactive feature. It should feel like exploring a map, not reading a spreadsheet.

**Implementation plan:**

1. **Data fetch:** On mount, fetch all published objects and edges from the API. For 25 nodes and 77 edges, this fits in a single payload. At scale, paginate or use a graph-specific endpoint.

2. **Node representation:**
   ```typescript
   interface GraphNode {
     id: string;
     slug: string;
     title: string;
     type: 'concept_note' | 'skill_guide' | 'project_blueprint';
     domain: string;
     stage: string;
     difficulty: number;
     risk_band: string;
     beginner_safe: boolean;
   }
   ```

3. **Edge representation:**
   ```typescript
   interface GraphEdge {
     source: string;
     target: string;
     type: 'prerequisite_for' | 'next_step_for';
   }
   ```

4. **Layout forces:**
   - Center gravity
   - Link force (stronger for prerequisite edges)
   - Collision avoidance
   - Domain clustering (custom force grouping nodes by domain)

5. **Visual encoding:**
   - Node color → type (concept=steel blue, skill=forest green, project=amber)
   - Node size → connection degree
   - Node border → risk band (green/amber/red)
   - Edge style → prerequisite=solid arrow, navigation=dashed
   - Label → title (shown on hover or at zoom level)

6. **Interaction:**
   - Hover → tooltip with title, type, plain language
   - Click → sidebar detail panel
   - Double-click → navigate to detail page
   - Drag → reposition node
   - Zoom → semantic detail levels
   - Filter → dim/hide nodes that don't match

7. **Domain clustering:** Use a custom force that pulls nodes toward domain-specific centers. This creates visible clusters (foundation, water, food, shelter, power, community) without rigid positioning.

### Future: 3D or layered view

At scale (100+ nodes), consider a layered view where:
- Layer 1 (bottom): concepts
- Layer 2 (middle): skills
- Layer 3 (top): projects

Prerequisites flow upward, creating a visible competence stack.

---

## 9. Offline and print strategy

### Print stylesheets

Every object detail page includes `@media print` rules that:
- Hide navigation, sidebar, interactive elements
- Render full content body
- Show all structured data (tools, materials, steps, criteria)
- Include a QR code linking back to the live version
- Format as a clean single-page field reference

### Offline kits

The `/offline` page offers downloadable bundles:

| Format | Contents | Use case |
|--------|----------|----------|
| **PDF field guide** | Selected domain or learning path, all objects as formatted pages | Print and carry |
| **EPUB** | Same content as reflowable ebook | E-reader or phone |
| **JSON export** | Raw graph data + object content | Developer/contributor use |
| **Printable worksheets** | Just the worksheet/checklist artifacts from each object | Workshop handouts |

Generation: The backend's `PublicationService.export_static_bundle()` produces these from canonical content. The website provides download links.

### Progressive web app (optional, v2)

Service worker caches visited pages and the full graph data for offline browsing. Not required for v1 but the architecture supports it.

---

## 10. API integration patterns

### Server-side (Astro SSR)

```typescript
// src/lib/api.ts
const API_BASE = import.meta.env.PUBLIC_API_URL || 'http://localhost:8100';

export async function fetchPublicObject(slug: string): Promise<PublicObjectResponse> {
  const res = await fetch(`${API_BASE}/v1/public/objects/${slug}`);
  if (!res.ok) throw new Error(`Object not found: ${slug}`);
  return res.json();
}
```

```astro
---
// src/pages/explore/[slug].astro
import { fetchPublicObject } from '@/lib/api';
import ContentLayout from '@/layouts/ContentLayout.astro';
import ObjectDetail from '@/components/sections/ObjectDetail.astro';

const { slug } = Astro.params;
const object = await fetchPublicObject(slug);
---
<ContentLayout title={object.title}>
  <ObjectDetail object={object} />
</ContentLayout>
```

### Client-side (React islands)

```typescript
// src/islands/SearchPanel.tsx
import { useState, useEffect } from 'react';
import type { SearchResponse, SearchRequest } from '@/lib/types';

export default function SearchPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [filters, setFilters] = useState<Partial<SearchRequest>>({});

  async function handleSearch() {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, ...filters }),
    });
    setResults(await res.json());
  }

  // ... render
}
```

### Proxy pattern

For client-side API calls, use an Astro API route as a proxy to avoid CORS and hide the backend URL:

```typescript
// src/pages/api/search.ts
export async function POST({ request }) {
  const body = await request.json();
  const res = await fetch(`${API_BASE}/v1/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return new Response(res.body, { headers: { 'Content-Type': 'application/json' } });
}
```

---

## 11. Project structure

```text
capability-commons-web/
├── astro.config.mjs
├── package.json
├── tsconfig.json
├── public/
│   ├── fonts/
│   ├── icons/
│   └── og-image.png
├── src/
│   ├── layouts/
│   │   ├── BaseLayout.astro
│   │   ├── ContentLayout.astro
│   │   └── ExplorerLayout.astro
│   ├── pages/
│   │   ├── index.astro                    # Landing
│   │   ├── about.astro                    # Doctrine + project context
│   │   ├── explore/
│   │   │   ├── index.astro                # Graph explorer
│   │   │   └── [slug].astro               # Object detail
│   │   │   └── [slug]/
│   │   │       └── bundle.astro           # Six-part bundle
│   │   ├── domains/
│   │   │   ├── index.astro                # Domain grid
│   │   │   └── [domain].astro             # Single domain
│   │   ├── paths/
│   │   │   ├── index.astro                # Learning path index
│   │   │   └── [slug].astro               # Learning path detail
│   │   ├── search.astro                   # Search page
│   │   ├── ask.astro                      # AI tutor
│   │   ├── rings.astro                    # Ring navigator
│   │   ├── syllabus/
│   │   │   ├── index.astro                # 12-week overview
│   │   │   └── [week].astro               # Single week
│   │   ├── glossary.astro                 # Zero-jargon glossary
│   │   ├── offline.astro                  # Offline kits
│   │   ├── contribute/
│   │   │   ├── index.astro                # Contribution landing
│   │   │   ├── field-report.astro         # Submit field report
│   │   │   └── adaptation.astro           # Submit adaptation
│   │   └── api/                           # Proxy routes
│   │       ├── search.ts
│   │       ├── retrieve.ts
│   │       └── graph.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.astro
│   │   │   ├── Footer.astro
│   │   │   ├── Sidebar.astro
│   │   │   └── Breadcrumbs.astro
│   │   ├── sections/
│   │   │   ├── HeroLanding.astro
│   │   │   ├── DoctrineStrip.astro
│   │   │   ├── StatsStrip.astro
│   │   │   ├── DomainGrid.astro
│   │   │   ├── EntryPoints.astro
│   │   │   ├── ObjectDetail.astro
│   │   │   ├── StructuredPayload.astro
│   │   │   ├── PrerequisiteTree.astro
│   │   │   ├── NextSteps.astro
│   │   │   ├── CitationList.astro
│   │   │   ├── ContradictionBanner.astro
│   │   │   ├── TeachForwardCard.astro
│   │   │   ├── SyllabusTimeline.astro
│   │   │   └── ObjectCard.astro
│   │   └── ui/
│   │       ├── StatusBadge.astro
│   │       ├── FacetPills.astro
│   │       ├── DifficultyBar.astro
│   │       ├── RiskBadge.astro
│   │       └── Button.astro
│   ├── islands/
│   │   ├── GraphExplorer.tsx
│   │   ├── SearchPanel.tsx
│   │   ├── AskTutor.tsx
│   │   ├── BundleViewer.tsx
│   │   ├── FilterBar.tsx
│   │   ├── RingExplorer.tsx
│   │   └── ProgressTracker.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   ├── types.ts
│   │   ├── graph.ts
│   │   ├── filters.ts
│   │   └── config.ts
│   └── styles/
│       ├── global.css
│       ├── tokens.css
│       ├── typography.css
│       └── print.css
```

---

## 12. Implementation phases

### Phase W1: Foundation (week 1)

**Goal:** Astro project scaffolded, API client working, base layout rendering.

- [ ] Initialize Astro 5 project with React integration, SSR adapter
- [ ] Set up design tokens, global styles, typography
- [ ] Build `BaseLayout`, `Header`, `Footer`
- [ ] Build `api.ts` fetch wrapper with typed responses
- [ ] Build `types.ts` mirroring Pydantic schemas
- [ ] Build landing page with static hero, doctrine strip, stats strip
- [ ] Verify API connectivity: fetch and render one public object

### Phase W2: Content pages (week 2)

**Goal:** All knowledge objects browsable and readable.

- [ ] Build `ObjectDetail.astro` with all sections
- [ ] Build `StructuredPayload.astro` (type-specific rendering for skill/concept/project)
- [ ] Build `StatusBadge`, `FacetPills`, `DifficultyBar`, `RiskBadge` UI components
- [ ] Build `PrerequisiteTree` and `NextSteps` components
- [ ] Build `CitationList` and `ContradictionBanner`
- [ ] Build `/explore/[slug]` page consuming public object API
- [ ] Build `DomainGrid` and `/domains` pages
- [ ] Build `ObjectCard` for list views

### Phase W3: Graph explorer (week 3)

**Goal:** Interactive D3 force graph working.

- [ ] Build `GraphExplorer.tsx` React island
- [ ] Implement D3 force layout with domain clustering
- [ ] Add node color/size encoding by type/connections
- [ ] Add edge rendering (solid prerequisite, dashed navigation)
- [ ] Add hover tooltips and click → sidebar detail
- [ ] Add filter sidebar (domain, stage, type)
- [ ] Add search highlight integration
- [ ] Build `/explore` page mounting the graph explorer
- [ ] Test with full 25-node seed graph

### Phase W4: Search and navigation (week 4)

**Goal:** Search working, learning paths browsable, ring navigator functional.

- [ ] Build `SearchPanel.tsx` React island
- [ ] Build proxy route `/api/search.ts`
- [ ] Implement facet filter sidebar
- [ ] Build `/search` page
- [ ] Build `PathCard` and `/paths` index page
- [ ] Build `/paths/[slug]` with ordered step view
- [ ] Build `SyllabusTimeline` and `/syllabus` pages
- [ ] Build `RingExplorer.tsx` and `/rings` page

### Phase W5: AI tutor and bundles (week 5)

**Goal:** Retrieval-grounded Q&A and six-part bundles working.

- [ ] Build `AskTutor.tsx` React island
- [ ] Build proxy route `/api/retrieve.ts`
- [ ] Implement intent selector and context panel
- [ ] Build response rendering with citations and recommended objects
- [ ] Build `/ask` page
- [ ] Build `BundleViewer.tsx` for tabbed hook/primer/guide/reference/worksheet/teach-forward
- [ ] Build `/explore/[slug]/bundle` page

### Phase W6: Polish and offline (week 6)

**Goal:** Print styles, offline kits, glossary, contribution forms, deployment.

- [ ] Build `print.css` for clean printing
- [ ] Build `/glossary` page (aggregated from structured_data)
- [ ] Build `/offline` page with download links
- [ ] Build `/contribute` pages with field report and adaptation forms
- [ ] Build `ProgressTracker.tsx` (localStorage-based)
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Performance audit (Core Web Vitals)
- [ ] Deploy to hosting (Cloudflare Pages, Vercel, or Replit)

---

## 13. Deployment strategy

### Option A: Replit (match existing pattern)

Both the personal site and GAMUT are deployed on Replit. Deploy the Capability Commons website as a separate Replit project running the Astro SSR build.

**Pros:** Consistent with existing deployment pattern, simple.
**Cons:** Replit SSR performance may be limited; cold starts.

### Option B: Cloudflare Pages + Workers

Astro has a native Cloudflare adapter. Static pages served from CDN, SSR pages run on Workers.

**Pros:** Fast, global, generous free tier, edge-rendered.
**Cons:** Slightly more setup.

### Option C: Vercel

Astro has a native Vercel adapter. ISR for public content, serverless functions for API proxies.

**Pros:** Good DX, built-in analytics.
**Cons:** Lock-in, cost at scale.

### Recommendation

Start with **Replit** for consistency and ease of iteration. Move to Cloudflare Pages when performance or scale matters.

### Backend hosting

The FastAPI backend needs its own deployment (separate from the website). Options:
- Replit (current local dev setup)
- Railway or Render (managed Postgres + Python)
- Docker on a VPS

The website connects to the backend via `PUBLIC_API_URL` environment variable.

---

## 14. Success criteria for v1

| Criterion | Metric |
|-----------|--------|
| All 25 seed objects browsable | Every slug renders a complete detail page |
| Graph explorer functional | D3 graph loads, filters work, click-through to detail works |
| Search returns results | FTS search returns relevant objects with facet filtering |
| Learning paths navigable | At least 1 complete path renders with ordered steps |
| AI tutor answers questions | At least 3 intents return grounded, cited answers |
| Mobile responsive | All pages usable on 375px viewport |
| Print clean | Object detail pages print as usable field references |
| Lighthouse score | Performance ≥ 90, Accessibility ≥ 95 |
| Time to interactive | < 2s on 3G for static pages |

---

## 15. Open questions

1. **Name and domain:** "Capability Commons" is a working title. Final name and domain TBD. The Astro config's `site` field and all external references should use a constant.
2. **Auth for contributors:** The backend has API key auth. The website contributor forms need a flow for obtaining/using keys. Simplest v1: a shared contributor key with rate limiting.
3. **Content authoring:** Should the website include an admin interface for creating/editing objects, or is that CLI/API-only for now? Recommendation: CLI + API for v1, admin UI as a v2 feature.
4. **Image/media hosting:** Knowledge objects may need diagrams, photos, and worksheets. The backend has `object_files` + object storage. The website needs a media rendering strategy (direct object-store URLs or proxied).
5. **Analytics:** What to measure beyond Core Web Vitals? Recommendation: track page views per object, search queries, graph explorer usage, and tutor interactions. Use a privacy-respecting tool (Plausible, Umami).

---

## Relationship to the personal site

The personal site at `jasonstgeorge.com` already has Capability Commons wired as an endorsed satellite in `ENDORSED_PROPERTIES`. The URL constant `CAPABILITY_COMMONS_URL` currently points to `/work#capability-commons` on the personal site. When this website deploys:

1. Change one line in `src/lib/site.ts`:
   ```typescript
   export const CAPABILITY_COMMONS_URL = 'https://capabilitycommons.org'; // or final domain
   ```
2. This auto-updates the homepage FeatureGrid card, Footer, AssociatedProperties, SelectedWorkPreview, and About page FocusGrid.
3. Optionally add to the header utility nav (same pattern as GAMUT).

The personal site case study on the Work page (`/work#capability-commons`) remains as context for how this project fits into the broader body of work.
