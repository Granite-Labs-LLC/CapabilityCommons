# FE-003: Server-Side Search with UX Filters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the client-side graph-node filtering in SearchPanel with server-side `POST /v1/search` calls, adding new UX filter controls for cost band, risk band, difficulty, housing type, and climate zone.

**Architecture:** Update the `SearchRequest` type to include a `filters` field matching the backend's `PublicSearchFilters`, update the `SearchHit` type to match the backend response, modify SearchPanel to debounce queries to the server, and add new filter controls. Keep the existing graph-node data as initial suggestions and fallback when the backend is unreachable.

**Tech Stack:** TypeScript, React 19, Astro 6

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/site/src/lib/types.ts` | Modify | Update `SearchRequest` with `filters` field, update `SearchHit` with new fields |
| `apps/site/src/lib/api.ts` | Modify | Add `searchPublic()` with mock fallback |
| `apps/site/src/islands/SearchPanel.tsx` | Modify | Server-side search with debounce, new filter UI |
| `apps/site/src/styles/search-panel.css` | Modify | Styles for new filter controls |
| `apps/site/src/pages/search.astro` | Modify | Pass apiBase prop |

---

### Task 1: Update search types in types.ts

**Files:**
- Modify: `apps/site/src/lib/types.ts`

- [ ] **Step 1: Add PublicSearchFilters and update SearchRequest**

In `apps/site/src/lib/types.ts`, find:

```typescript
export interface SearchRequest {
  query: string;
  facet_filters?: Record<string, string[]>;
  top_k?: number;
  object_types?: string[];
  only_published?: boolean;
}
```

Replace with:

```typescript
export interface PublicSearchFilters {
  stage?: string;
  difficulty_max?: number;
  cost_band?: string;
  risk_band?: string;
  beginner_safe?: boolean;
  housing_type?: string;
  climate_zone?: string;
  settlement_type?: string;
}

export interface SearchRequest {
  query: string;
  facet_filters?: Record<string, string[]>;
  filters?: PublicSearchFilters;
  top_k?: number;
  object_types?: string[];
  only_published?: boolean;
}
```

- [ ] **Step 2: Update SearchHit to include new backend fields**

Find:

```typescript
export interface SearchHit {
  object_id: string;
  version_id: string;
  slug: string;
  title: string;
  type: string;
  plain_language: string;
  score: number;
  facets: Record<string, string[]>;
}
```

Replace with:

```typescript
export interface SearchHit {
  object_id: string;
  version_id: string;
  slug: string;
  title: string;
  type: string;
  summary_short: string | null;
  plain_language: string;
  score: number;
  lifecycle_state: string;
  validity_status: string;
  facets: Record<string, string[]>;
}
```

- [ ] **Step 3: Verify the build still works**

```bash
cd apps/site && npx astro check 2>&1 | tail -5
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site
git add src/lib/types.ts
git commit -m "feat: add PublicSearchFilters type and update SearchHit (FE-003)"
```

---

### Task 2: Add searchPublic() to api.ts

**Files:**
- Modify: `apps/site/src/lib/api.ts`

- [ ] **Step 1: Add searchPublic function with mock fallback**

In `apps/site/src/lib/api.ts`, add the following after the existing `search()` function (after line 72, or after `askPublic` if FE-002 was applied first):

```typescript
export async function searchPublic(params: SearchRequest): Promise<SearchResponse> {
  return withMockFallback(
    () => apiFetch('/v1/search', {
      method: 'POST',
      body: JSON.stringify({ ...params, only_published: true }),
    }),
    () => {
      // Fall back to client-side filtering of mock data
      const q = params.query.toLowerCase().trim();
      const hits = MOCK_OBJECTS
        .filter((obj) => {
          if (!q) return true;
          return obj.title.toLowerCase().includes(q)
            || obj.plain_language.toLowerCase().includes(q);
        })
        .map((obj, i) => ({
          object_id: obj.slug,
          version_id: `v-${obj.slug}`,
          slug: obj.slug,
          title: obj.title,
          type: obj.type,
          summary_short: obj.summary_short,
          plain_language: obj.plain_language,
          score: 1 - i * 0.05,
          lifecycle_state: 'published',
          validity_status: 'valid',
          facets: obj.facets,
        }));
      return { query: params.query, top_k: params.top_k || 20, hits };
    },
  );
}
```

- [ ] **Step 2: Update the imports if SearchRequest is not already imported**

The existing `search()` function already imports `SearchRequest` and `SearchResponse` from types — verify they're in the import block. If `PublicSearchFilters` was added to types but is not used in api.ts, no additional import is needed (it's used within `SearchRequest`).

- [ ] **Step 3: Verify the build still works**

```bash
cd apps/site && npx astro check 2>&1 | tail -5
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site
git add src/lib/api.ts
git commit -m "feat: add searchPublic() with mock fallback (FE-003)"
```

---

### Task 3: Rewrite SearchPanel for server-side search

**Files:**
- Modify: `apps/site/src/islands/SearchPanel.tsx`

- [ ] **Step 1: Replace the entire SearchPanel.tsx file**

Replace the contents of `apps/site/src/islands/SearchPanel.tsx` with:

```tsx
import { useState, useCallback, useEffect, useRef } from 'react';
import type { GraphNode, SearchHit, PublicSearchFilters } from '../lib/types';

const TYPE_LABELS: Record<string, string> = {
  concept_note: 'Concept',
  skill_guide: 'Skill',
  project_blueprint: 'Project',
};

const TYPE_COLORS: Record<string, string> = {
  concept_note: '#4a6fa5',
  skill_guide: '#2c5f2d',
  project_blueprint: '#b8860b',
};

const STAGES = ['foundation', 'household', 'productive', 'community', 'advanced'];
const COST_BANDS = ['free', 'low', 'medium', 'high'];
const RISK_BANDS = ['low', 'moderate', 'high', 'expert_only'];
const HOUSING_TYPES = ['renter', 'homeowner', 'apartment', 'house', 'mobile_home'];
const CLIMATE_ZONES = ['cold', 'temperate', 'hot_humid', 'arid'];

interface Props {
  nodes: GraphNode[];
  suggestedQueries: string[];
  apiBase: string;
}

export default function SearchPanel({ nodes, suggestedQueries, apiBase }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<PublicSearchFilters>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const allDomains = [...new Set(nodes.map((n) => n.domain))].sort();
  const allTypes = [...new Set(nodes.map((n) => n.type))].sort();

  const [domainFilter, setDomainFilter] = useState<Set<string>>(new Set());
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());

  const hasFilters = Object.values(filters).some((v) => v !== undefined) ||
    domainFilter.size > 0 || typeFilter.size > 0;

  const executeSearch = useCallback(async (q: string, f: PublicSearchFilters, domains: Set<string>, types: Set<string>) => {
    if (!q.trim() && !Object.values(f).some((v) => v !== undefined) && domains.size === 0 && types.size === 0) {
      setResults(null);
      return;
    }

    setLoading(true);
    try {
      const facetFilters: Record<string, string[]> = {};
      if (domains.size > 0) facetFilters.domain = [...domains];

      const objectTypes = types.size > 0 ? [...types] : undefined;

      const res = await fetch(`${apiBase}/v1/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q.trim() || '*',
          filters: Object.values(f).some((v) => v !== undefined) ? f : undefined,
          facet_filters: Object.keys(facetFilters).length > 0 ? facetFilters : undefined,
          object_types: objectTypes,
          only_published: true,
          top_k: 50,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setResults(data.hits);
      } else {
        // Fall back to client-side filtering
        setResults(clientSideSearch(q, f, domains, types, nodes));
      }
    } catch {
      setResults(clientSideSearch(q, f, domains, types, nodes));
    }
    setLoading(false);
  }, [apiBase, nodes]);

  // Debounced search on query or filter change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      executeSearch(query, filters, domainFilter, typeFilter);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, filters, domainFilter, typeFilter, executeSearch]);

  const clearAll = useCallback(() => {
    setQuery('');
    setFilters({});
    setDomainFilter(new Set());
    setTypeFilter(new Set());
    setResults(null);
  }, []);

  const toggleDomain = useCallback((d: string) => {
    setDomainFilter((prev) => {
      const next = new Set(prev);
      if (next.has(d)) next.delete(d); else next.add(d);
      return next;
    });
  }, []);

  const toggleType = useCallback((t: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });
  }, []);

  return (
    <div className="search-panel">
      <div className="search-panel__bar">
        <input
          type="search"
          className="search-panel__input"
          placeholder="What do you need to know how to do?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <button
          className={`search-panel__filter-toggle ${showFilters ? 'search-panel__filter-toggle--active' : ''}`}
          onClick={() => setShowFilters(!showFilters)}
        >
          Filters {hasFilters && '(active)'}
        </button>
      </div>

      {showFilters && (
        <div className="search-panel__filters">
          <FilterChips title="Domain" items={allDomains} active={domainFilter} onToggle={toggleDomain} />
          <FilterChips title="Type" items={allTypes} active={typeFilter} labels={TYPE_LABELS} onToggle={toggleType} />
          <FilterChips title="Stage" items={STAGES} active={new Set(filters.stage ? [filters.stage] : [])}
            onToggle={(v) => setFilters((prev) => ({ ...prev, stage: prev.stage === v ? undefined : v }))} />
          <FilterChips title="Cost" items={COST_BANDS} active={new Set(filters.cost_band ? [filters.cost_band] : [])}
            onToggle={(v) => setFilters((prev) => ({ ...prev, cost_band: prev.cost_band === v ? undefined : v }))} />
          <FilterChips title="Risk" items={RISK_BANDS} active={new Set(filters.risk_band ? [filters.risk_band] : [])}
            labels={{ low: 'Low', moderate: 'Moderate', high: 'High', expert_only: 'Expert only' }}
            onToggle={(v) => setFilters((prev) => ({ ...prev, risk_band: prev.risk_band === v ? undefined : v }))} />

          <div className="search-panel__select-row">
            <SelectFilter label="Max difficulty" value={filters.difficulty_max?.toString() || ''}
              options={[['1', '1'], ['2', '2'], ['3', '3'], ['4', '4'], ['5', '5']]}
              onChange={(v) => setFilters((prev) => ({ ...prev, difficulty_max: v ? Number(v) : undefined }))} />
            <SelectFilter label="Housing" value={filters.housing_type || ''}
              options={HOUSING_TYPES.map((h) => [h, h.replace('_', ' ')])}
              onChange={(v) => setFilters((prev) => ({ ...prev, housing_type: v || undefined }))} />
            <SelectFilter label="Climate" value={filters.climate_zone || ''}
              options={CLIMATE_ZONES.map((c) => [c, c.replace('_', ' ')])}
              onChange={(v) => setFilters((prev) => ({ ...prev, climate_zone: v || undefined }))} />
          </div>

          <label className="search-panel__toggle-label">
            <input
              type="checkbox"
              checked={filters.beginner_safe || false}
              onChange={(e) => setFilters((prev) => ({ ...prev, beginner_safe: e.target.checked || undefined }))}
            />
            Beginner safe only
          </label>

          {hasFilters && (
            <button className="search-panel__clear" onClick={clearAll}>
              Clear all filters
            </button>
          )}
        </div>
      )}

      {loading && (
        <div className="search-panel__loading">Searching...</div>
      )}

      {!loading && results === null ? (
        <div className="search-panel__suggestions">
          <p className="search-panel__suggestions-label">Try searching for:</p>
          <div className="search-panel__suggestions-list">
            {suggestedQueries.map((sq) => (
              <button key={sq} className="search-panel__suggestion" onClick={() => setQuery(sq)}>
                "{sq}"
              </button>
            ))}
          </div>
        </div>
      ) : !loading && results !== null && results.length === 0 ? (
        <div className="search-panel__empty">
          <p>No results for "{query}"{hasFilters ? ' with current filters' : ''}.</p>
          <p>Try different terms or <button className="search-panel__link-btn" onClick={clearAll}>clear your search</button>.</p>
        </div>
      ) : !loading && results !== null ? (
        <div className="search-panel__results">
          <p className="search-panel__count">{results.length} result{results.length !== 1 ? 's' : ''}</p>
          <div className="search-panel__grid">
            {results.map((r) => (
              <a key={r.slug} href={`/explore/${r.slug}`} className="search-result-card">
                <div className="search-result-card__header">
                  <span className="search-result-card__type" style={{ background: TYPE_COLORS[r.type] || '#666' }}>
                    {TYPE_LABELS[r.type] || r.type}
                  </span>
                  {r.facets?.domain?.[0] && <span className="search-result-card__domain">{r.facets.domain[0]}</span>}
                  {r.facets?.stage?.[0] && <span className="search-result-card__stage">{r.facets.stage[0]}</span>}
                </div>
                <h3 className="search-result-card__title">{r.title}</h3>
                <p className="search-result-card__text">{r.plain_language}</p>
                <div className="search-result-card__footer">
                  <span className="search-result-card__score">
                    {(r.score * 100).toFixed(0)}% match
                  </span>
                </div>
              </a>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function FilterChips({
  title, items, active, labels, onToggle,
}: {
  title: string;
  items: string[];
  active: Set<string>;
  labels?: Record<string, string>;
  onToggle: (v: string) => void;
}) {
  return (
    <div className="search-panel__chip-group">
      <span className="search-panel__chip-label">{title}</span>
      <div className="search-panel__chips">
        {items.map((item) => (
          <button
            key={item}
            className={`search-panel__chip ${active.has(item) ? 'search-panel__chip--active' : ''}`}
            onClick={() => onToggle(item)}
          >
            {labels?.[item] || item}
          </button>
        ))}
      </div>
    </div>
  );
}

function SelectFilter({
  label, value, options, onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (v: string) => void;
}) {
  return (
    <div className="search-panel__select-filter">
      <label className="search-panel__select-label">{label}</label>
      <select className="search-panel__select" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Any</option>
        {options.map(([val, display]) => <option key={val} value={val}>{display}</option>)}
      </select>
    </div>
  );
}

function clientSideSearch(
  query: string,
  filters: PublicSearchFilters,
  domains: Set<string>,
  types: Set<string>,
  nodes: GraphNode[],
): SearchHit[] {
  const q = query.toLowerCase().trim();
  return nodes
    .filter((n) => {
      if (domains.size > 0 && !domains.has(n.domain)) return false;
      if (types.size > 0 && !types.has(n.type)) return false;
      if (filters.stage && n.stage !== filters.stage) return false;
      if (filters.beginner_safe && !n.beginner_safe) return false;
      if (filters.risk_band && n.risk_band !== filters.risk_band) return false;
      if (filters.difficulty_max && n.difficulty > filters.difficulty_max) return false;
      if (q) {
        return n.title.toLowerCase().includes(q)
          || n.plain_language.toLowerCase().includes(q)
          || n.domain.toLowerCase().includes(q);
      }
      return true;
    })
    .map((n) => {
      let score = 0.5;
      if (q) {
        if (n.title.toLowerCase().includes(q)) score += 0.3;
        if (n.plain_language.toLowerCase().includes(q)) score += 0.15;
        if (n.domain.toLowerCase().includes(q)) score += 0.05;
      }
      return {
        object_id: n.id,
        version_id: `v-${n.id}`,
        slug: n.slug,
        title: n.title,
        type: n.type,
        summary_short: null,
        plain_language: n.plain_language,
        score,
        lifecycle_state: 'published',
        validity_status: 'valid',
        facets: { domain: [n.domain], stage: [n.stage] },
      };
    })
    .sort((a, b) => b.score - a.score);
}
```

- [ ] **Step 2: Verify the build still works**

```bash
cd apps/site && npx astro check 2>&1 | tail -5
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site
git add src/islands/SearchPanel.tsx
git commit -m "feat: rewrite SearchPanel for server-side search with UX filters (FE-003)"
```

---

### Task 4: Update search.astro to pass apiBase

**Files:**
- Modify: `apps/site/src/pages/search.astro`

- [ ] **Step 1: Update the search page to pass apiBase**

Replace the contents of `apps/site/src/pages/search.astro` with:

```astro
---
import BaseLayout from '@/layouts/BaseLayout.astro';
import SearchPanel from '@/islands/SearchPanel';
import { getGraphData } from '@/lib/api';
import { API_BASE } from '@/lib/config';
import '@/styles/search-panel.css';

const { nodes } = await getGraphData();
const suggestedQueries = [
  'How do I keep my house warm during an outage?',
  'What tools do I need for basic repair?',
  'Low-cost water storage for renters',
  'Calculate backup power runtime',
  'Getting started with food preservation',
  'Community resource mapping',
];
---

<BaseLayout title="Search — Capability Commons">
  <section class="search-page">
    <div class="container">
      <h1>Search</h1>
      <p class="search-page__desc">
        Find capabilities by plain-language query. Filter by domain, stage, type, and context.
      </p>
      <SearchPanel nodes={nodes} suggestedQueries={suggestedQueries} apiBase={API_BASE} client:load />
    </div>
  </section>
</BaseLayout>

<style>
  .search-page {
    padding-block: var(--sp-16);
  }

  .search-page h1 { margin-bottom: var(--sp-4); }

  .search-page__desc {
    color: var(--color-muted);
    margin-bottom: var(--sp-8);
    max-width: var(--content-width);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site
git add src/pages/search.astro
git commit -m "feat: pass apiBase to SearchPanel for server-side search (FE-003)"
```

---

### Task 5: Add CSS for new filter controls

**Files:**
- Modify: `apps/site/src/styles/search-panel.css`

- [ ] **Step 1: Add styles for new controls**

Append the following to the end of `apps/site/src/styles/search-panel.css`:

```css
/* --- FE-003: Server-side search filter additions --- */

.search-panel__loading {
  text-align: center;
  padding: var(--sp-8);
  color: var(--color-muted, #666);
  font-style: italic;
}

.search-panel__select-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  margin-top: var(--sp-3);
}

.search-panel__select-filter {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 140px;
}

.search-panel__select-label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-muted, #666);
}

.search-panel__select {
  padding: var(--sp-1) var(--sp-2);
  border: 1px solid var(--color-border, #ddd);
  border-radius: var(--radius-sm, 4px);
  background: var(--color-surface, #fff);
  font-size: 0.9rem;
}

.search-panel__select:focus {
  outline: 2px solid var(--color-primary, #4a6fa5);
  outline-offset: 1px;
}

.search-result-card__score {
  font-size: 0.8rem;
  color: var(--color-muted, #666);
  font-weight: 500;
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site
git add src/styles/search-panel.css
git commit -m "style: add CSS for server-side search filter controls (FE-003)"
```

---

### Task 6: Build verification

- [ ] **Step 1: Full build**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons/apps/site && npm run build 2>&1 | tail -10
```

Expected: Astro build completes, output in `dist/`

- [ ] **Step 2: Verify dist includes search page**

```bash
ls apps/site/dist/search/index.html
```

Expected: File exists

- [ ] **Step 3: Return to repo root and verify backend tests still pass**

```bash
cd /Users/nuggylover1210/Projects/CapabilityCommons
.venv/bin/python -m pytest tests/ --ignore=tests/test_integration.py -q 2>&1 | tail -5
```

Expected: All tests pass
