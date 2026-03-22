# Capability Commons — Architecture & Vision

> **Last updated:** 2026-03-22
>
> AI should be used to convert hidden competence into shared public capacity.

This document captures the full current state of the Capability Commons project: what it is, why it exists, how it works, and where it's going. It serves as the canonical reference for anyone building on, deploying, or extending the system.

---

## Table of Contents

1. [Vision & Problem Statement](#1-vision--problem-statement)
2. [Doctrine](#2-doctrine)
3. [Knowledge Model](#3-knowledge-model)
4. [System Architecture](#4-system-architecture)
5. [Backend: CapabilityCommons](#5-backend-capabilitycommons)
6. [Frontend: CapabilityCommonsSite](#6-frontend-capabilitycommonssite)
7. [Data Model](#7-data-model)
8. [API Surface](#8-api-surface)
9. [Search & Retrieval](#9-search--retrieval)
10. [Seed Data & Content Pipeline](#10-seed-data--content-pipeline)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Security & Access Control](#12-security--access-control)
13. [Current State & Statistics](#13-current-state--statistics)
14. [Roadmap](#14-roadmap)

---

## 1. Vision & Problem Statement

### The Problem

Practical knowledge — how to store water safely, size a backup power system, seal a drafty house, grow food, verify a claim before acting on it — is trapped inside trades, institutions, guilds, paywalls, jargon, and credential barriers. Most adults cannot maintain the systems their households depend on.

### The Thesis

The unit of value is not the article. It is the **reproducible capability**: a node in a knowledge graph that explains something people need to understand, trains something people need to do, or produces something people can keep, use, and teach forward.

### What Capability Commons Is

An open knowledge architecture that maps **concepts to skills, skills to projects, projects to local deployment, and every learner to teach-forward transmission**. The system is a public capability stack — not a content feed, not a course platform, not a wiki. It is a structured graph of practical competence designed to lower barriers to self-sufficiency.

### What It Is Not

- Not an LMS or course marketplace
- Not an encyclopedia or wiki
- Not a social platform
- Not a collection of articles organized by topic

It is a **knowledge graph with pedagogical semantics**, where every node has prerequisites, context constraints, assessment criteria, and a path to teach-forward transmission.

---

## 2. Doctrine

Six rules govern the commons:

| # | Rule | Meaning |
|---|------|---------|
| 1 | **Open by default** | The core corpus is freely accessible |
| 2 | **Practical before ornamental** | Every lesson terminates in action |
| 3 | **Layered for beginners** | No topic requires insider language to start |
| 4 | **Locally adaptable** | Climate, region, budget, and available tools matter |
| 5 | **Project-based** | Competence comes from making, repairing, measuring, building |
| 6 | **Teach-forward** | Every learner becomes a transmitter |

### Assessment Philosophy

Competence is measured by action, not abstract testing:

- **Artifact exists** — the learner produced something usable
- **Performance demonstrated** — the learner can do the thing
- **Oral explanation** — the learner can explain it clearly
- **Teach-forward** — the learner can pass it on

Rubric progression: Incomplete → Emerging → Functional → Teach-forward ready.

### AI's Role

AI serves as compiler and tutor, not oracle:

- **Translation** — expert language into plain language
- **Personalization** — adapt paths for context (renter, rural, low-budget)
- **Graph navigation** — what to learn next and why
- **Localization** — adjust for climate, materials, available tools
- **Conversion** — one source into many forms (article → checklist → workshop)

> AI may draft, map, compare, and explain. Human-reviewed evidence decides canon.

### Five-Format Publishing Rule

Every core topic should exist in five forms:

1. **Hook** — short, compelling entry point (poster, 90-second pitch)
2. **Primer** — plain-language explanation
3. **Guide** — step-by-step practical instructions
4. **Reference** — specs, formulas, diagrams, checklists
5. **Teach-forward kit** — how to pass it on to someone else

---

## 3. Knowledge Model

### Three Interlocking Graphs

The system is not a pile of documents. It is three graphs working together:

| Graph | Question it answers | Examples |
|-------|-------------------|----------|
| **Concept graph** | What things mean, how ideas relate | *"What is thermal mass?" "How does voltage relate to power?"* |
| **Skill graph** | What people can do, what they must know first | *"What can I do next?" "What must I know before wiring a subpanel?"* |
| **Deployment graph** | Where, when, under what constraints something is useful | *"How does this work for renters?" "What's the low-cost version?"* |

### Capability Domains

The corpus is organized by **civilizational function**, not academic discipline:

| Layer | Domains | Example Capabilities |
|-------|---------|---------------------|
| **Foundation** | Epistemics, AI/tool use, measurement, systems thinking | Verify & cite, AI-grounded research, systems mapping |
| **Household** | Water, food, shelter, power | Safe storage, pantry rotation, weatherization, load audit |
| **Productive** | Gardening, preservation, repair, fabrication | Seed starting, safe preservation, hand tool literacy |
| **Community** | Mutual aid, local mapping, coordination | Local resource map, teach-forward sessions |
| **Advanced** | Energy systems, networking, governance | Backup power planning, community resilience |

### Concentric Ring Entry Model

People start with immediate needs and expand outward:

| Ring | Label | Question |
|------|-------|----------|
| 1 | **Stay functional** | How do I keep myself and my household stable? |
| 2 | **Repair and maintain** | How do I stop being helpless around systems? |
| 3 | **Produce** | How do I make useful things and reduce dependency? |
| 4 | **Coordinate** | How do we scale from household to community resilience? |
| 5 | **Steward and transmit** | How do we preserve competence across generations? |

### Knowledge Object Types

| Type | Purpose | Key Structured Fields |
|------|---------|----------------------|
| **concept_note** | Explains a principle or model | definition, key_questions, misconceptions, formulas |
| **skill_guide** | Observable action a learner can perform | performance_statement, tools, materials, steps, success_criteria, failure_modes, safety_boundary |
| **project_blueprint** | Applied task that produces a useful artifact | goal, deliverables, acceptance_criteria, time_box, budget |
| **module** | One teachable unit (usually one week) | week, node_refs, learning_objectives, lab, field_task, teach_forward_task, delivery_profile |
| **assessment** | Checks competence via action | assessment_type, rubric, passing_threshold, evidence_required |

The system also defines 13 additional types for future expansion: worksheet, reference_sheet, glossary, teach_forward_packet, learning_path, field_report, local_adaptation, expert_review, correction, safety_notice, translation, community_map, resource_directory.

### Edge Types

25 typed directed edges capture relationships between knowledge objects:

| Category | Edge Types | Purpose |
|----------|-----------|---------|
| **Learning path** | `prerequisite_for`, `next_step_for`, `builds_on`, `contains` | Sequencing and navigation |
| **Curriculum** | `assessed_by`, `validated_by` | Assessment and evidence |
| **Content** | `alternative_to`, `supported_by`, `derived_from`, `quotes`, `summarizes` | Content relationships |
| **Versioning** | `corrected_by`, `contradicted_by`, `deprecated_by`, `supersedes` | Truth maintenance |
| **Localization** | `translated_from`, `forked_from`, `adapted_for`, `applies_in` | Context adaptation |
| **Constraints** | `requires_tool`, `requires_material`, `has_failure_mode`, `mitigated_by`, `unsafe_without`, `bounded_by` | Safety and resources |

---

## 4. System Architecture

### High-Level Overview

```
┌────────────────────────────────────────────────┐
│              CapabilityCommonsSite             │
│           (Astro 5 · Static Output)            │
│                                                │
│   Build time:                                  │
│     Fetches /v1/public/objects → static HTML   │
│     Fetches /v1/public/graph  → graph data     │
│     Generates one page per knowledge object    │
│                                                │
│   Runtime (React islands):                     │
│     Graph explorer ──── D3 force-directed      │
│     Search panel ────── POST /v1/search        │
│     AI tutor ────────── POST /v1/retrieve/*    │
│     Ring explorer ───── client-side filtering  │
│     Bundle viewer ───── tabbed content viewer  │
└────────────────┬───────────────────────────────┘
                 │ HTTPS
                 ▼
┌────────────────────────────────────────────────┐
│              CapabilityCommons                 │
│          (FastAPI · Python 3.11+)              │
│                                                │
│   Public API:     /v1/public/*   (no auth)     │
│   Search:         /v1/search     (no auth)     │
│   Retrieval:      /v1/retrieve/* (no auth)     │
│   CRUD:           /v1/objects/*  (API key)     │
│   Edges:          /v1/edges      (API key)     │
│   Evidence:       /v1/evidence/* (API key)     │
│   Reviews:        /v1/reviews    (API key)     │
│   Health:         /health        (no auth)     │
│                                                │
│   Background:                                  │
│     Outbox worker → reindex → embed            │
└────────────────┬───────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────┐
│          PostgreSQL 16 + pgvector              │
│                                                │
│   19 tables · 30+ enum types                   │
│   Full-text search (TSVECTOR)                  │
│   Vector embeddings (1536-dim, ivfflat)        │
│   JSONB structured data (schema-per-type)      │
│   Event sourcing (outbox pattern)              │
└────────────────────────────────────────────────┘
```

### Design Decision: Why "Agentic Data Lite"

The system is built on a **trimmed "Agentic Data Lite"** architecture rather than a Neo4j-first approach. The reasoning:

The hardest problem is not graph traversal. It is **maintaining truth, versioning, and fit-to-context over time**. That requires:

- Provenance and citation tracking
- Version-aware supersession
- Contradiction handling and resolution
- Evidence-pack assembly for AI retrieval
- Locality and context adaptation
- Teach-forward and curriculum semantics

Postgres is the canonical source of truth. Graph traversal happens via relational edge tables. Neo4j remains an option as a derived graph projection layer for future multi-hop queries at scale.

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend framework** | FastAPI 0.115+ | Async API with OpenAPI docs |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe database access |
| **Database** | PostgreSQL 16 + pgvector | Source of truth, FTS, embeddings |
| **Migrations** | Alembic | Schema versioning |
| **Validation** | Pydantic 2.12+ | Request/response schemas |
| **Embeddings** | OpenAI text-embedding-3-small | Optional vector search (1536 dims) |
| **Containerization** | Docker + Docker Compose | Portable deployment |
| **Frontend framework** | Astro 5 (static output) | Pages, routing, SSR data fetching |
| **Interactive islands** | React 19 | Graph, search, AI tutor, rings, bundles |
| **Graph visualization** | D3.js 7 | Force-directed knowledge graph |
| **Styling** | CSS custom properties | Design tokens, responsive, print |
| **Fonts** | Source Serif 4, Inter, JetBrains Mono | Body, UI, code typography |

---

## 5. Backend: CapabilityCommons

### Project Layout

```
CapabilityCommons/
├── src/capability_commons/
│   ├── main.py                    # FastAPI app, middleware, error handlers
│   ├── config.py                  # Settings from .env (pydantic-settings)
│   ├── api/
│   │   ├── router.py              # Route aggregation
│   │   ├── deps.py                # Dependency injection (db, auth, workspace)
│   │   ├── auth.py                # API key hashing, resolution
│   │   ├── health.py              # /health and /health/detailed
│   │   ├── objects.py             # CRUD for knowledge objects
│   │   ├── entities.py            # Named entity management
│   │   ├── edges.py               # Typed graph edges
│   │   ├── evidence.py            # Sources, spans, citations
│   │   ├── reviews.py             # Quality workflow, contradictions
│   │   ├── search.py              # Full-text + hybrid search
│   │   ├── retrieval.py           # Intent-based evidence packing
│   │   └── public.py              # Unauthenticated public reads
│   ├── db/
│   │   ├── models.py              # 19 SQLAlchemy ORM models
│   │   └── session.py             # Async session factory
│   ├── domain/
│   │   └── enums.py               # 30+ domain enums
│   ├── services/
│   │   ├── registry.py            # Object & version lifecycle
│   │   ├── entity.py              # Entity operations
│   │   ├── evidence.py            # Evidence sourcing & provenance
│   │   ├── review.py              # Review & contradiction workflow
│   │   ├── embedding.py           # Pluggable embedding provider
│   │   ├── publication.py         # Public rendering & graph building
│   │   ├── helpers.py             # Shared utilities
│   │   └── exceptions.py          # AppError, NotFoundError, etc.
│   ├── search/
│   │   ├── indexer.py             # Text chunking & segment creation
│   │   └── adapters/
│   │       └── postgres_search.py # FTS with websearch_to_tsquery
│   ├── graph/
│   │   └── adapters/
│   │       └── relational_graph.py # BFS traversal, path finding
│   ├── retrieval/
│   │   ├── planner.py             # Intent → edge-type mapping & reranking
│   │   └── service.py             # Evidence pack assembly
│   ├── schemas/                   # Pydantic request/response models
│   ├── middleware/
│   │   ├── rate_limit.py          # Per-minute quota enforcement
│   │   └── logging.py             # Request logging with request IDs
│   └── cli/
│       ├── seed.py                # Two-pass idempotent graph loader
│       ├── worker.py              # Outbox event consumer
│       └── keys.py                # API key management
├── alembic/                       # 3 migration versions
├── expanded_seed/                 # 25 capability nodes + 77 edges
├── capability_commons_module_seed_pack_v1/  # 24 curriculum nodes + 98 edges
├── tests/                         # 17 test modules
├── docker-compose.yml             # Postgres 16 + FastAPI
├── Dockerfile                     # Python 3.14-slim
└── pyproject.toml                 # Dependencies & metadata
```

### Service Layer

The backend follows a clean **router → service → database** architecture:

- **Routers** handle HTTP, validation, and dependency injection
- **Services** contain business logic and domain rules
- **Models** define the database schema with SQLAlchemy 2 async ORM
- **Adapters** provide pluggable implementations for search, graph, and embeddings

Key services:

| Service | Responsibility |
|---------|---------------|
| **RegistryService** | Object/version lifecycle (create, draft, publish, deprecate) |
| **EvidenceService** | Sources, citations, spans, provenance tracking |
| **ReviewService** | Editorial/expert/safety review, contradiction cases |
| **EmbeddingService** | Pluggable vector encoding (OpenAI default) |
| **PublicationService** | Public API rendering, graph data assembly |
| **RetrievalService** | Intent-aware evidence pack compilation |

### Middleware Stack

Applied in order on every request:

1. **CORSMiddleware** — configurable origins (default: `localhost:4321`)
2. **RequestLoggingMiddleware** — access log with method, path, status, elapsed_ms, request_id
3. **RateLimitMiddleware** — per-minute quota by API key or IP (100 req/min default, 300 for public)

### Event Sourcing

All significant state changes emit `OutboxEvent` records (JSONB payload). The background worker polls for unprocessed events and dispatches handlers:

- `version.published` → reindex version (chunk text into segments)
- `version.reindexed` → generate embeddings (batch OpenAI calls)

This decouples write-path latency from expensive operations like embedding generation.

---

## 6. Frontend: CapabilityCommonsSite

### Project Layout

```
CapabilityCommonsSite/
├── src/
│   ├── layouts/
│   │   └── BaseLayout.astro        # HTML shell, head, Header + Footer
│   ├── pages/                      # 16+ routes
│   │   ├── index.astro             # Landing page
│   │   ├── about.astro             # Doctrine, rings, AI role, metrics
│   │   ├── search.astro            # Search with suggestions
│   │   ├── ask.astro               # AI tutor with intent selection
│   │   ├── rings.astro             # Concentric ring navigator
│   │   ├── explore/
│   │   │   ├── index.astro         # D3 graph explorer + object grid
│   │   │   ├── [slug].astro        # Object detail (dynamic, API-driven)
│   │   │   └── [slug]/bundle.astro # Six-part module bundle
│   │   ├── domains/
│   │   │   ├── index.astro         # Domain grid
│   │   │   └── [domain].astro      # Domain detail (dynamic)
│   │   ├── paths/
│   │   │   └── index.astro         # Learning path index
│   │   └── syllabus/
│   │       └── index.astro         # 12-week curriculum timeline
│   ├── components/
│   │   ├── layout/                 # Header, Footer
│   │   ├── sections/               # 13 page-level components
│   │   └── ui/                     # 5 reusable primitives
│   ├── islands/                    # 5 React interactive components
│   │   ├── GraphExplorer.tsx       # D3 force-directed graph
│   │   ├── SearchPanel.tsx         # Client-side search + filters
│   │   ├── AskTutor.tsx            # AI question answering
│   │   ├── BundleViewer.tsx        # Six-part tabbed content viewer
│   │   └── RingExplorer.tsx        # SVG concentric ring navigator
│   ├── lib/
│   │   ├── api.ts                  # Typed fetch wrapper + mock fallback
│   │   ├── types.ts                # TypeScript types mirroring Pydantic
│   │   ├── config.ts               # Site metadata, doctrine, domains, stats
│   │   └── mock.ts                 # 7 mock objects for offline dev
│   └── styles/
│       ├── tokens.css              # Design tokens (colors, spacing, type)
│       ├── typography.css          # Font imports, heading styles
│       ├── global.css              # Resets, base styles, container
│       ├── graph-explorer.css      # GraphExplorer island styles
│       ├── search-panel.css        # SearchPanel island styles
│       ├── ask-tutor.css           # AskTutor island styles
│       ├── bundle-viewer.css       # BundleViewer island styles
│       ├── ring-explorer.css       # RingExplorer island styles
│       └── print.css               # Print-friendly overrides
├── public/                         # Static assets (favicon, icons)
├── astro.config.mjs                # Static output, React integration
├── package.json                    # Astro 6, React 19, D3 7
└── tsconfig.json                   # Strict mode, @/ path alias
```

### Build Model

The site uses **Astro's static output mode** — all pages are pre-rendered to HTML at build time:

1. **Build time**: Astro calls `getStaticPaths()` on dynamic routes, fetching all object slugs from the API. Each slug generates a static HTML page. Graph data is fetched once and cached in-memory across pages.

2. **Runtime**: Five React islands hydrate on the client for interactivity. Search and AI tutor make live API calls from the user's browser. The graph explorer, ring navigator, and bundle viewer work with data embedded at build time.

3. **Mock fallback**: If the API is unreachable at build time, `withMockFallback()` catches the error and returns 7 sample objects. The site still builds (~70 pages with mock vs ~120+ with live data).

### Dynamic Routes

Three pages use `getStaticPaths()` for pre-rendering:

| Route | Data Source | Pages Generated |
|-------|-----------|-----------------|
| `/explore/[slug]` | `listPublicObjects()` → one page per object | 49 (with live API) |
| `/explore/[slug]/bundle` | `listPublicObjects()` → one bundle per object | 49 |
| `/domains/[domain]` | `DOMAINS` config → one page per domain | 6 |

### React Islands

| Island | Purpose | Data Source |
|--------|---------|------------|
| **GraphExplorer** | D3 force-directed graph with domain clustering, filtering, zoom/pan | Build-time graph data (props) |
| **SearchPanel** | Client-side full-text search with domain/type/stage filters | Build-time graph nodes (props) |
| **AskTutor** | Intent-based AI question answering with context facets | Live API calls (`POST /v1/retrieve/evidence_pack`) |
| **BundleViewer** | Six-tab content viewer (Hook, Primer, Guide, Reference, Worksheet, Teach Forward) | Build-time bundle data (props) |
| **RingExplorer** | SVG concentric ring visualizer mapping nodes to 5 rings by stage | Build-time graph nodes (props) |

### Design System

The visual identity is **warm, serious, and high-contrast** — not gamified, not corporate.

| Token | Value | Purpose |
|-------|-------|---------|
| **Accent** | `#2c5f2d` (forest green) | Growth, practical capability |
| **Surface** | `#faf8f5` (warm off-white) | Page background |
| **Body font** | Source Serif 4 | Serious, readable, not generic |
| **UI font** | Inter | Clean, functional |
| **Code font** | JetBrains Mono | Technical content |

Type badge colors: blue (concept), green (skill), amber (project), purple (module), orange (assessment).

Risk band colors: green (low) → amber (moderate) → red (high) → dark red (expert only).

---

## 7. Data Model

### Database Schema (19 Tables)

**Core domain:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `workspaces` | Multi-tenant container | slug, visibility, language |
| `context_objects` | Versioned knowledge objects | slug, co_type, lifecycle_state, visibility |
| `context_object_versions` | Immutable version snapshots | title, summary, plain_language, markdown_body, structured_data (JSONB), full_text (TSVECTOR) |
| `context_object_facets` | Contextual metadata | facet_type (domain/audience/housing/settlement/budget/climate), facet_value |
| `entities` | Named concepts, tools, standards | entity_type, canonical_name, aliases, metadata |
| `context_object_entities` | Cross-reference | mention_count, role_labels |

**Graph & evidence:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `edges` | 25 typed directed relationships | edge_type, confidence, provenance_method, validity_status |
| `evidence_sources` | Provenance records | source_kind (URL/FILE/BOOK/STANDARD/...), trust_tier, citation_text |
| `evidence_spans` | Char-span citations | start_char, end_char, excerpt, checksum |
| `edge_evidence_spans` | Junction: edges ↔ evidence | edge_id, evidence_span_id |

**Review & quality:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `review_records` | Quality assessments | review_type (editorial/expert/pedagogy/safety), outcome, commentary |
| `contradiction_cases` | Dimension-based conflicts | dimension (factual/safety/currency/regional), severity, resolution |

**Content indexing:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `content_segments` | Chunked text with embeddings | ordinal, text_content, embedding (vector 1536), token_count |

**Retrieval observability:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `retrieval_runs` | Intent-driven search sessions | intent, status, step count |
| `retrieval_steps` | Execution trace | step_type (resolve_seeds/search/graph_traversal/rerank/finalize) |

**Operations:**

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `api_keys` | Bearer token auth | key_hash (SHA256), workspace_id, revoked_at |
| `rate_limit_log` | Request counting | key_hash, window_start, request_count |
| `outbox_events` | Event sourcing | aggregate_type, event_type, payload (JSONB), processed_at |
| `object_files` | Object storage references | media_type, byte_size, checksum, label |

### Lifecycle States

Objects follow a governed lifecycle:

```
DRAFT → IN_REVIEW → REVIEWED → VERIFIED → PUBLISHED → DEPRECATED → ARCHIVED
```

Only `PUBLISHED` objects appear in the public API. Versioning is immutable — each edit creates a new `ContextObjectVersion` with a `supersedes_version_id` pointer.

### Structured Data

Each object type has a validated JSONB schema in `structured_data`. This allows extensibility without migrations:

- **skill_guide**: performance_statement, inputs, tools, materials, steps_summary, success_criteria, failure_modes, safety_boundary
- **project_blueprint**: goal, deliverables, acceptance_criteria, time_box_hours, budget_band, team_size
- **module**: week, node_refs, learning_objectives, seminar_outline, lab, field_task, teach_forward_task, delivery_profile
- **assessment**: assessment_type, rubric, passing_threshold, evidence_required

---

## 8. API Surface

### Public Endpoints (No Auth)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/health/detailed` | Database, search, graph adapter health |
| `GET` | `/v1/public/objects` | List all published objects |
| `GET` | `/v1/public/objects/{slug}` | Object detail with facets, entities, citations |
| `GET` | `/v1/public/objects/{slug}/bundle` | Six-part curriculum bundle |
| `GET` | `/v1/public/graph` | Graph nodes + edges for D3 visualization |
| `GET` | `/v1/public/modules/{slug}` | Module detail |
| `GET` | `/v1/public/paths/{slug}` | Learning path with ordered steps |
| `POST` | `/v1/search` | Full-text + optional hybrid search with facet filters |
| `POST` | `/v1/retrieve/evidence_pack` | Intent-based evidence assembly |
| `GET` | `/v1/retrieval_runs/{id}` | Retrieval run metadata |
| `GET` | `/v1/retrieval_runs/{id}/steps` | Execution trace |

### Authenticated Endpoints (API Key Required)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/objects` | Paginated object list (cursor-based) |
| `POST` | `/v1/objects` | Create object |
| `POST` | `/v1/objects/{id}/versions` | Create new version |
| `PATCH` | `/v1/objects/{id}/versions/{vid}` | Update draft version |
| `POST` | `/v1/objects/{id}/versions/{vid}/publish` | Publish version |
| `POST` | `/v1/entities` | Create named entity |
| `POST` | `/v1/entities/{id}/aliases` | Add entity alias |
| `POST` | `/v1/edges` | Create typed edge |
| `GET` | `/v1/edges` | Query edges (filter by src, dst, type) |
| `POST` | `/v1/evidence/sources` | Register evidence source |
| `POST` | `/v1/evidence/spans` | Create citation span |
| `POST` | `/v1/evidence/edge_citations` | Link evidence to edge |
| `GET` | `/v1/objects/{oid}/versions/{vid}/citations` | List citations |
| `POST` | `/v1/reviews` | Submit review |
| `POST` | `/v1/contradictions` | Open contradiction case |
| `POST` | `/v1/contradictions/{id}/resolve` | Resolve contradiction |
| `POST` | `/v1/objects/{oid}/versions/{vid}/verify` | Mark verified |
| `POST` | `/v1/objects/{oid}/versions/{vid}/dispute` | Mark disputed |
| `POST` | `/v1/objects/{oid}/versions/{vid}/deprecate` | Propose deprecation |

---

## 9. Search & Retrieval

### Search Architecture

**Primary**: PostgreSQL full-text search using `websearch_to_tsquery` with `ts_rank` scoring. Supports AND/OR operators, facet filtering (EXISTS subqueries on `context_object_facets`), and filtering by object type, lifecycle state, and visibility.

**Secondary** (optional): Vector embeddings via pgvector (1536-dim, ivfflat index). Enabled when `OPENAI_API_KEY` is configured. The embedding pipeline:

1. `version.published` → outbox event
2. Worker chunks text (900 chars max, 150-char overlap, paragraph-boundary splitting)
3. Creates `content_segment` rows
4. `version.reindexed` → outbox event
5. Worker calls OpenAI batch embedding (50 segments/batch)
6. Stores vectors in `content_segment.embedding`

### Retrieval Planner

The retrieval system is **intent-aware** — different user intents activate different graph traversal strategies:

| Intent | Edge Types Activated | Use Case |
|--------|---------------------|----------|
| `how_to` | supported_by, requires_tool, requires_material, has_failure_mode, mitigated_by, bounded_by | Practical task completion |
| `learn_path` | prerequisite_for, next_step_for, builds_on, contains | Learning sequence navigation |
| `why` | supported_by, derived_from, validated_by, contradicted_by | Understanding reasoning |
| `compare_options` | alternative_to, applies_in, adapted_for, bounded_by | Decision making |
| `localize` | adapted_for, applies_in, bounded_by, alternative_to | Context-specific adaptation |
| `debug_failure` | has_failure_mode, mitigated_by, contradicted_by, supported_by | Troubleshooting |
| `teach_forward` | contains, next_step_for, assessed_by | Teaching preparation |
| `what_changed` | supersedes, corrected_by, deprecated_by, contradicted_by | Change tracking |
| `safety_check` | unsafe_without, bounded_by, mitigated_by, contradicted_by, validated_by | Safety verification |

Each retrieval run executes a pipeline: **resolve seeds → search → graph traversal → rerank → finalize**, tracked in `retrieval_runs` and `retrieval_steps` for observability.

Reranking weights: search_score 45%, published_bonus 15%, verified_bonus 0–15%, facet_match 15%, citation_bonus 0–10%.

---

## 10. Seed Data & Content Pipeline

### Two-Pass Seeding

The knowledge graph is loaded idempotently in two passes:

**Pass 1: Capabilities** (`expanded_seed/`)
- 25 objects across 7 domains (foundation, water, food, shelter, repair, power, community)
- Types: skill_guide, concept_note, project_blueprint
- 50 prerequisite edges from YAML `requires` fields
- 27 navigation edges from `imports/edges.csv`

**Pass 2: Curriculum** (`capability_commons_module_seed_pack_v1/`)
- 12 modules + 12 assessments = 24 objects
- 98 edges from `imports/edges.csv` (COVERS, ASSESSED_BY, EVALUATES, PRECEDES)
- Links modules to the capability nodes they cover

### Seed Data Format

Each node is a YAML file in `canonical/nodes/`:

```yaml
id: water.safe-storage
type: skill
title: "Emergency Water Storage"
summary: "Store minimum 72-hour emergency water supply..."
plain_language: "Learn how to safely store enough drinking water..."
primary_domain: water
domains: [water]
stage: household
difficulty: 2
cost_band: low
risk_band: low
contexts: [general, renter, homeowner, urban, rural]
requires: [foundation.verify-and-cite]
lifecycle_state: published
payload:
  performance_statement: "Store minimum 72-hour supply..."
  tools: [...]
  materials: [...]
  success_criteria: [...]
  failure_modes: [...]
  safety_boundary: "..."
```

Edges are CSV:

```csv
source_id,target_id,edge_type,sequence,condition
module.01-truth-tools-and-ai,foundation.verify-and-cite,COVERS,1,
module.01-truth-tools-and-ai,foundation.ai-grounded-research,COVERS,2,
assessment.module.01,module.01-truth-tools-and-ai,ASSESSED_BY,,
```

### Type Mapping

| Seed Type | Database COType |
|-----------|----------------|
| skill | SKILL_GUIDE |
| concept | CONCEPT_NOTE |
| project | PROJECT_BLUEPRINT |
| module | MODULE |
| assessment | ASSESSMENT |

| Seed Edge | Database EdgeType |
|-----------|------------------|
| REQUIRES | prerequisite_for |
| NEXT | next_step_for |
| COVERS | contains |
| ASSESSED_BY | assessed_by |
| EVALUATES | validated_by |
| PRECEDES | next_step_for |

### Facet Extraction

The seeder maps context labels to typed facets:

| Context | Facet Type | Facet Value |
|---------|-----------|-------------|
| general, renter, homeowner | AUDIENCE | general, renter, homeowner |
| urban, rural, off_grid | SETTLEMENT_TYPE | urban, rural, off_grid |
| low_budget | BUDGET_PROFILE | low_budget |
| *primary_domain* | DOMAIN | water, food, shelter, etc. |

---

## 11. Deployment Architecture

### Production Topology

```
┌─────────────────────────────────┐     ┌─────────────────────────────────┐
│    Linux Server (Backend)       │     │    Replit (Frontend)             │
│                                 │     │                                 │
│    Caddy (auto-SSL)             │     │    npm run build                │
│      ↓                          │ ←── │      Fetches /v1/public/*       │
│    FastAPI (:8100)              │     │      Generates static HTML      │
│      ↓                          │     │                                 │
│    PostgreSQL 16 + pgvector     │     │    npx serve dist               │
│                                 │     │      Serves static pages        │
│    Outbox worker (optional)     │     │      React islands → live API   │
│                                 │     │                                 │
│    ufw: 22, 80, 443 only       │     │    Custom domain (optional)     │
└─────────────────────────────────┘     └─────────────────────────────────┘
```

### Backend Deployment (Linux)

- **Docker Compose** with production overrides (`docker-compose.prod.yml`)
- **Caddy** reverse proxy for automatic SSL via Let's Encrypt (nginx + certbot as alternative)
- **Firewall**: ports 22 (SSH), 80 (HTTP redirect), 443 (HTTPS) only; port 8100 not exposed
- **Backups**: automated daily `pg_dump` with 14-day retention via cron
- **Health monitoring**: `/health` endpoint for uptime checks

### Frontend Deployment (Replit)

- **Static build**: `npm run build` generates ~120+ HTML pages from live API
- **Serve**: `npx serve dist -l 3000` or Replit Static Deployment
- **Secrets**: `PUBLIC_API_URL` and `SITE` set as Replit Secrets
- **CORS**: Backend `CORS_ORIGINS` must include the Replit URL
- **Rebuild required**: After seeding new data on the backend (static pages don't update automatically)

### Environment Variables

**Backend (.env):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `CORS_ORIGINS` | `["http://localhost:4321"]` | Allowed frontend origins |
| `RATE_LIMIT_PER_MINUTE` | `100` | Authenticated rate limit |
| `RATE_LIMIT_PUBLIC_PER_MINUTE` | `300` | Public rate limit |
| `OPENAI_API_KEY` | (empty) | Optional, for vector embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI model for embeddings |
| `APP_ENV` | `development` | Environment mode |

**Frontend (.env):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `PUBLIC_API_URL` | `http://localhost:8100` | Backend API URL |
| `SITE` | `http://localhost:4321` | Canonical site URL (OG tags, sitemap) |

See [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md) for the full deployment sequence.

---

## 12. Security & Access Control

### Authentication

- API keys in `cc_{urlsafe_token_32}` format
- SHA256 hashed storage (raw key shown once at creation)
- Bearer token via `Authorization` header
- Each key scoped to one workspace
- Revocation support (soft delete via `revoked_at`)
- Auth optional in dev mode (`AUTH_ENABLED=false`)

### Authorization Model

- **Public endpoints** (`/v1/public/*`, `/v1/search`, `/v1/retrieve/*`): no auth required
- **Mutation endpoints** (`/v1/objects`, `/v1/edges`, `/v1/evidence`, `/v1/reviews`): API key required
- **Workspace isolation**: all mutations scoped to the key's workspace

### Rate Limiting

- Atomic per-minute counting via `INSERT ... ON CONFLICT DO UPDATE`
- Configurable limits per API key (100/min default) and public IP (300/min default)
- Automatic cleanup of rate limit logs older than 1 hour (via outbox worker)
- 429 Too Many Requests response on exceed

### CORS

- Configurable via `CORS_ORIGINS` environment variable
- Must include all frontend deployment URLs
- Credentials, headers, and methods are permissive for the configured origins

---

## 13. Current State & Statistics

### Seeded Graph (v1)

| Metric | Count |
|--------|-------|
| Knowledge objects | 49 (25 capabilities + 24 curriculum) |
| Object types active | 5 (concept_note, skill_guide, project_blueprint, module, assessment) |
| Capability domains | 7 (foundation, water, food, shelter, repair, power, community) |
| Prerequisite edges | 75 |
| Navigation + curriculum edges | 100 |
| Total edges | 175 |
| Edge types active | 5 (prerequisite_for, next_step_for, contains, assessed_by, validated_by) |
| Facets | 167+ across 4 types |
| Syllabus weeks | 12 |

### Domain Distribution

| Domain | Object Count | Capabilities |
|--------|-------------|-------------|
| Foundation | 5 | Verify & cite, AI research, measurement, systems mapping, household inventory |
| Water | 4 | Safe storage, treatment selection, basic testing, household water plan |
| Food | 5 | Pantry design, pantry rotation, safe preservation, seed starting, beginner garden |
| Shelter | 3 | Building envelope, weatherization audit, moisture & mold control |
| Repair | 2 | Hand tool literacy, shutoffs seals & patches |
| Power | 4 | Circuit basics, load audit, runtime calculation, backup power plan |
| Community | 2 | Local resource map, teach-forward session |

### 12-Week Curriculum

| Week | Module | Domain |
|------|--------|--------|
| 1 | Truth, Tools & AI | Foundation |
| 2 | Measure, Map & Inventory | Foundation |
| 3 | Water Storage & Treatment | Water |
| 4 | Water Testing & Planning | Water |
| 5 | Pantry Rotation & Preservation | Food |
| 6 | Seed Starting & Garden Planning | Food |
| 7 | Envelope & Weatherization | Shelter |
| 8 | Moisture, Tools, Shutoffs & Patching | Shelter/Repair |
| 9 | Circuit Basics & Label Reading | Power |
| 10 | Load Audit & Runtime | Power |
| 11 | Backup Power & Local Resource Map | Power/Community |
| 12 | Capstone: Teach Forward | Community |

### Codebase Statistics

| Component | Metric |
|-----------|--------|
| Backend source | ~68 Python files, ~5,300 lines |
| Backend tests | 17 test modules |
| Database tables | 19 |
| Database enums | 30+ |
| API endpoints | 30+ routes across 8 modules |
| Alembic migrations | 3 |
| Frontend pages | 16+ routes |
| React islands | 5 |
| Section components | 13 |
| UI primitives | 5 |
| Design tokens | 60+ CSS custom properties |

### Implementation Status

All planned phases are complete:

| Phase | Focus | Status |
|-------|-------|--------|
| Backend core | Object lifecycle, edges, evidence, reviews | Complete |
| Auth & rate limiting | API keys, workspace isolation, per-minute quotas | Complete |
| Search | FTS + optional hybrid vector search | Complete |
| Retrieval planner | Intent-based evidence assembly | Complete |
| Public API | Graph, objects, modules, bundles, paths | Complete |
| Seed pipeline | Two-pass idempotent loader (capabilities + curriculum) | Complete |
| Frontend W1 | Foundation — design system, landing page, 9 routes | Complete |
| Frontend W2 | Content — object detail, structured payloads, domains | Complete |
| Frontend W3 | Graph explorer — D3 force-directed with domain clustering | Complete |
| Frontend W4 | Search, ring navigator, learning paths, syllabus | Complete |
| Frontend W5 | AI tutor, module bundles | Complete |
| Frontend W6 | Print styles, offline stubs, contribute pages | Complete |
| Live integration | Dynamic routes from API, module/assessment support | Complete |
| Documentation | Deploy guides (Linux, Replit), deploy checklist | Complete |

---

## 14. Roadmap

### Near-Term Enhancements

- **Offline kits**: generate downloadable PDFs and print-friendly bundles from published objects
- **Learning paths**: curated multi-step sequences beyond the linear 12-week syllabus
- **Glossary**: auto-generated from entity names and definitions
- **Custom domain**: production frontend URL (capabilitycommons.org)
- **Monitoring**: Grafana dashboard for API latency and error rates

### Medium-Term Growth

- **Content expansion**: additional domains (health, communications, sanitation, heat/cooling)
- **Field reports**: community-submitted local adaptations and observations
- **Expert review workflow**: structured peer review with editorial, pedagogy, and safety tracks
- **Contradiction resolution**: active management of conflicting guidance across regions/contexts
- **Version diffing**: show what changed between object versions
- **Neo4j projection**: derived graph layer for complex multi-hop queries at scale

### Long-Term Vision

- **Regional forks**: localized knowledge graphs for specific climates, regulations, materials
- **Offline-first mobile**: PWA or native app for field use without connectivity
- **Community-contributed content**: submission pipeline with editorial review
- **Institutional partnerships**: libraries, extension services, mutual aid networks as distribution channels
- **Competence credentialing**: verified teach-forward chains as informal credentials
- **Multi-language support**: translated corpora with provenance tracking back to source

### Architectural Principles for Growth

1. **Postgres stays canonical** — all other stores (Neo4j, OpenSearch, S3) are derived projections
2. **Pluggable adapters** — search, graph, and embedding providers can be swapped without touching business logic
3. **Event-driven side effects** — expensive operations (embedding, indexing, notifications) happen via the outbox, not in request paths
4. **Static-first frontend** — build-time rendering for SEO and performance; hydrate only what needs interactivity
5. **Seed-and-extend** — the content pipeline is idempotent and additive; new domains are new seed passes, not schema changes

---

## References

| Document | Location | Purpose |
|----------|----------|---------|
| Backend README | `CapabilityCommons/README.md` | Quick start, API overview, project layout |
| Vision & Doctrine | `CapabilityCommons/docs/VISION.md` | Founding principles and knowledge model |
| Deploy Checklist | `CapabilityCommons/docs/DEPLOY_CHECKLIST.md` | End-to-end deployment sequence |
| Production Deploy | `CapabilityCommons/docs/PRODUCTION_DEPLOY.md` | Linux server deployment guide |
| Local Dev Deploy | `CapabilityCommons/docs/DEPLOY_GUIDE.md` | Loading graph and connecting frontend |
| Replit Deploy | `CapabilityCommonsSite/docs/REPLIT_DEPLOY.md` | Frontend deployment on Replit |
| Frontend README | `CapabilityCommonsSite/README.md` | Site architecture, pages, design system |
| Architectural Rationale | `CapabilityCommons/docs/context/CONTEXT.md` | Why Agentic Data Lite over Neo4j-first |
| Original Vision | `CapabilityCommons/docs/context/INIT.md` | Founding vision document (15 sections) |
| V1 Blueprint | `CapabilityCommons/docs/context/SEED.md` | Ontology, 25-node graph, 12-week syllabus |
| Seed Ontology | `CapabilityCommons/expanded_seed/schema/ontology_v1.md` | Field definitions for capability nodes |
| Curriculum Schema | `CapabilityCommons/capability_commons_module_seed_pack_v1/schema/ontology_v1.md` | Field definitions for modules/assessments |
