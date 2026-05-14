# Capability Commons Developer Blueprint

Prepared from the codebase in `CapabilityCommons.zip` on 2026-03-29.

## 1. Intended outcome

Turn Capability Commons from a solid knowledge backend into a **public capability engine** that helps ordinary people find, understand, and implement practical skills. The system should be able to ingest real source material with trustworthy provenance, publish structured capability objects, and answer plain-language questions with implementation-ready guidance.

The target product is not just retrieval. It is:

- trustworthy ingestion provenance
- implementation-ready public answers
- guided search and ask flows for non-experts
- print/offline action cards
- operational review gates for risky or contested content

## 2. Baseline assumptions for the implementation team

- Keep **PostgreSQL + pgvector + FastAPI + outbox worker** as the core platform.
- Keep `POST /v1/retrieve/evidence_pack` as the **operator and evaluation surface**.
- Add `POST /v1/public/ask` as the **end-user answer surface**.
- Build the missing public UI as a new `apps/site/` workspace in this repo.
- Treat a real multi-source ingest run and the gold-query benchmark as release gates, not stretch goals.

## 3. Current-state findings that drive the plan

These are the implementation findings that matter most for the handoff:

1. `src/capability_commons/cli/ingest/load.py` writes `lifecycle_state = "PUBLISHED"`, while `src/capability_commons/domain/enums.py` defines lowercase enum values such as `published`.
2. `src/capability_commons/cli/ingest/parse.py` currently assigns placeholder page ranges rather than true page-preserving ranges.
3. Segment identifiers are reused per source and later keyed globally in extract/draft/cite flows, which will collide in multi-source projects.
4. `src/capability_commons/cli/ingest/draft.py` validates only a thin subset of the draft object, so incomplete objects can still be written.
5. `src/capability_commons/cli/ingest/canonicalize.py` archives merged/split drafts but does not materialize replacement YAML objects.
6. `src/capability_commons/cli/seed.py` has two loader breaks: edge-type normalization is inconsistent, and `EvidenceSpan` metadata is written to a field the ORM does not define.
7. The ingest load path directly sets publish fields, which bypasses the outbox-driven index/embed path used by `RegistryService.publish_version()`.
8. `src/capability_commons/retrieval/service.py` still uses lexical search only, even though the search API already has a hybrid path.
9. `src/capability_commons/search/adapters/postgres_search.py` does not do true hybrid candidate union; vector search only reranks FTS hits.
10. Retrieval graph expansion is computed but not fed into rerank, so intent-aware traversal is mostly diagnostic.
11. The docs describe search/retrieval as public routes, but `src/capability_commons/api/deps.py` still requires a workspace header or bearer key for those flows.
12. The archive does **not** contain the actual frontend implementation; it contains the backend and the site scaffold docs only.

## 4. Product thesis to implement

The system should move from **document retrieval** to **implementation support**.

That means a good answer should tell the user:

- what to do first
- what tools or materials they need
- what the smallest viable version is
- what can go wrong
- how to know they succeeded
- when to stop and get expert help
- what to learn next

## 5. Target architecture

### 5.1 Ingestion lane

`source registry -> parse store -> globally unique provenance segments -> extraction rows -> canonical drafts -> citation linker -> review gate -> publish -> index/embed`

Key changes:

- provenance segments must be globally unique and page-accurate
- every drafted object must carry the segment lineage that created it
- canonicalization must write real merged/split outputs
- load/publish must use the same indexing pathway as the application service
- validation must become a true release gate

### 5.2 Retrieval and answer lane

`query -> context capture -> optional/auto intent -> hybrid search -> graph expansion -> rerank -> answer composer -> citations + contradictions + next steps -> follow-up state`

Key changes:

- real hybrid retrieval with lexical + vector candidate union
- graph-expanded candidates must compete in final ranking
- answer composition must be structured and implementation-oriented
- public answer flow must be separate from operator diagnostics

### 5.3 Public interface

The public interface should not be a bare chat box. It should have four entry modes:

- **Problem-first search** for queries like “no running water”, “small solar for phone and lights”, or “pantry rotation for outages”
- **Guided ask** for conversational help with optional context capture
- **Deep object pages** for people who want the full guide, evidence, and graph context
- **Print/offline action cards** for field use

## 6. Recommended public answer contract

Treat this as the target shape for `POST /v1/public/ask`:

```json
{
  "conversation_id": "uuid",
  "resolved_intent": "how_to",
  "query": "How do I set up a small backup power system for lights and a phone?",
  "answer": "Plain-language direct answer.",
  "action_now": [
    "Do a load audit for the exact devices you want to power."
  ],
  "implementation_plan": [
    {
      "step": 1,
      "title": "Measure the load",
      "why": "Avoid overspending or under-sizing.",
      "materials": [
        "plug-in watt meter",
        "notebook"
      ],
      "success_check": "You know watts and runtime target for each device.",
      "stop_conditions": [
        "Any device exceeds the rating of the planned inverter."
      ]
    }
  ],
  "safety": {
    "stop_conditions": [
      "Unknown household wiring condition",
      "Damaged battery or inverter"
    ],
    "when_to_get_help": [
      "Permanent wiring changes",
      "utility interconnection",
      "battery damage"
    ]
  },
  "citations": [
    {
      "source_title": "Capability Commons object or source",
      "excerpt": "Grounding excerpt"
    }
  ],
  "related_objects": [
    {
      "slug": "power.load-audit",
      "role": "prerequisite"
    }
  ],
  "uncertainties": [
    "Battery chemistry preference not specified."
  ]
}
```

## 7. Phase plan

### Phase 0 — Correctness Baseline

**Objective:** Make ingest, load, provenance, graph semantics, and access control trustworthy enough for a real pilot ingest.

**Tickets:**

- `ARCH-001` — Freeze public answer contract and repo layout
- `ING-001` — Normalize lifecycle enum casing across ingest, validate, and seed
- `ING-002` — Implement true page-preserving parse output
- `ING-003` — Make segment identifiers globally unique and preserve lineage from extract to cite
- `ING-004` — Enforce full canonical draft schema during Pass 2
- `ING-005` — Materialize merge and split decisions in canonicalization
- `GRAPH-001` — Normalize prerequisite and next-step edge direction semantics
- `SEED-001` — Normalize edge-type imports from YAML suggested_edges and edges.csv
- `SEED-002` — Add metadata_json to EvidenceSpan and persist citation provenance
- `PUB-001` — Make ingest-loaded published content trigger indexing and embeddings
- `QA-001` — Harden ingestion validation and make it schema-aware
- `API-SEC-001` — Protect retrieval run detail endpoints and keep run internals non-public
- `TEST-001` — Add regression tests for the ingest correctness fixes

**Exit criteria:** A multi-source project can run parse→load without collisions or casing errors; citations persist claim metadata; published ingest content is indexed and embedded; retrieval-run internals are not publicly exposed.

### Phase 1 — Retrieval Quality

**Objective:** Make search and retrieval actually surface the right objects and explain why.

**Tickets:**

- `SEARCH-001` — Implement real hybrid candidate union (lexical + vector)
- `SEARCH-002` — Index implementation fields, not just markdown_body
- `RET-001` — Use hybrid search from RetrievalService.execute_plan
- `RET-002` — Feed graph-expanded candidates into rerank and evidence assembly
- `RET-003` — Add score breakdowns and retrieval diagnostics
- `SEARCH-003` — Replace raw facet_filters-only public search contract with UX-oriented filters
- `EVAL-001` — Build a gold-query evaluation harness for search and ask

**Exit criteria:** Hybrid search uses lexical + vector union; graph expansion influences ranking; score breakdowns are visible; gold-query benchmark is in CI and passes agreed thresholds.

### Phase 2 — Public Answer Layer

**Objective:** Turn evidence packs into implementation-ready answers usable by ordinary people.

**Tickets:**

- `API-001` — Add a public workspace resolver for search and ask
- `API-002` — Create POST /v1/public/ask with a public-friendly response shape
- `RET-004` — Support intent auto-detection and optional intent selection
- `CONTENT-001` — Extend structured_data with implementation profile fields
- `RET-005` — Build a structured answer composer on top of evidence packs
- `RET-006` — Add conversation memory and follow-up state
- `PUB-002` — Enrich public object responses with implementation-profile projections

**Exit criteria:** Anonymous users can call /v1/public/ask against the public workspace; intent is optional; responses include action_now, implementation_plan, safety, citations, and uncertainties; conversation follow-ups work.

### Phase 3 — Public Interface

**Objective:** Ship the guided search/ask experience and print-friendly action cards.

**Tickets:**

- `FE-001` — Scaffold the public site in apps/site
- `FE-002` — Implement Guided Ask with optional intent and context capture
- `FE-003` — Build problem-first search and beginner-safe filtering
- `FE-004` — Render action cards, citation drawer, contradiction warnings, and related objects
- `FE-005` — Add print/offline action-card views
- `FE-006` — Add answer feedback, field-report capture, and analytics events

**Exit criteria:** apps/site builds in CI; /ask and /search are wired to the new public APIs; answer pages render citations/contradictions/action plans; print/offline views work.

### Phase 4 — Operational Scale

**Objective:** Add review queues, safety gates, analytics, caching, and accurate runbooks for launch.

**Tickets:**

- `ING-007` — Move ingest orchestration from filesystem-only to DB-backed jobs and review queues
- `SAFE-001` — Create publish gates and safety review workflow for higher-risk content
- `OBS-001` — Add dashboards and metrics for ingest quality and public answer quality
- `PERF-001` — Cache popular public search and ask responses
- `DOC-001` — Update operator docs, status docs, and launch runbooks to match the real implementation

**Exit criteria:** Ingest jobs and reviews are tracked in DB; high-risk content requires review gates; answer-quality metrics exist; public caching is active; runbooks describe the actual system.

## 8. Critical path

Do these in order:

1. Fix ingest correctness and loader parity first.
2. Freeze the public answer contract.
3. Upgrade search/retrieval quality before UI work.
4. Build the public answer endpoint and conversation layer.
5. Build the public interface once the API shape is stable.
6. Add review queues, safety gates, metrics, and caching before broad launch.

## 9. Team lanes

| Lane | Primary ownership | Core tickets |
|---|---|---|
| Backend / Platform | API contracts, access control, publish/index path, caching, review gates | ARCH-001, API-001, API-002, PUB-001, API-SEC-001, PERF-001, SAFE-001 |
| Data / Ingest | parse, lineage, canonical drafts, canonicalization, validation | ING-001 to ING-005, QA-001, ING-007 |
| Search / Retrieval | hybrid search, graph-aware rerank, answer composer, conversation memory | SEARCH-001 to SEARCH-003, RET-001 to RET-006, EVAL-001 |
| Frontend | apps/site, search, ask, answer rendering, print/offline | FE-001 to FE-006 |
| QA / Content | gold-query benchmark, safety checks, citation review, launch gates | QA-001, TEST-001, EVAL-001, SAFE-001, OBS-001 |

## 10. Release gates

The team should not call this launch-ready until the following are true:

- a real multi-source ingest run succeeds end-to-end
- validation catches malformed drafts, orphan citations, and edge-type errors
- published ingest content is indexed and embedded automatically
- public ask works anonymously against the public workspace
- public answers include action_now, implementation plan, safety, and citations
- the gold-query benchmark passes agreed relevance and grounding thresholds
- high-risk objects require explicit review before public publication

## 11. Non-functional requirements

- **Trustworthiness:** every actionable answer must be traceable to evidence or structured data
- **Accessibility:** plain language by default, mobile-first layout, beginner-safe filters
- **Latency:** keep the public path fast enough for everyday use; use caching for repeated public queries
- **Observability:** track answer usefulness, print/save rate, citation coverage, and validation failure rate
- **Governance:** separate public answers from operator diagnostics and keep review gates explicit

## 12. Backlog summary

- Total tickets: **38**
- P0 tickets: **13**
- P1 tickets: **18**
- P2 tickets: **7**

The detailed backlog with owners, dependencies, acceptance criteria, and file-by-file patch targets is included in the spreadsheet and CSV artifacts that accompany this blueprint.

## 13. First ten tickets to start immediately

- `ARCH-001` — Freeze public answer contract and repo layout
- `ING-001` — Normalize lifecycle enum casing across ingest, validate, and seed
- `ING-002` — Implement true page-preserving parse output
- `ING-003` — Make segment identifiers globally unique and preserve lineage from extract to cite
- `ING-004` — Enforce full canonical draft schema during Pass 2
- `ING-005` — Materialize merge and split decisions in canonicalization
- `GRAPH-001` — Normalize prerequisite and next-step edge direction semantics
- `SEED-001` — Normalize edge-type imports from YAML suggested_edges and edges.csv
- `SEED-002` — Add metadata_json to EvidenceSpan and persist citation provenance
- `PUB-001` — Make ingest-loaded published content trigger indexing and embeddings

## 14. Notes for the team

- Do **not** start broad frontend development until `ARCH-001`, `API-001`, `API-002`, `RET-004`, and `RET-005` are done.
- Do **not** trust the current docs that imply the site is already implemented in this archive.
- Treat `POST /v1/retrieve/evidence_pack` as the raw retrieval/debug surface and `POST /v1/public/ask` as the user-facing product surface.
- Keep the initial stack simple: Postgres/pgvector is still the right default. Do not jump to a new vector DB or graph DB until the current correctness and product-layer issues are resolved.
