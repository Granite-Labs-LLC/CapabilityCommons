I went through the repo in the zip. My read is: the foundation is real, but it is still better at **storing knowledge** than **delivering implementation-ready help**.

One important scope note: the actual frontend app is not in this archive, so I’m assessing the user interface from the retrieval/search API and the site scaffold docs, not from shipped UI code.

## Bottom line

This is a strong substrate for a public capability commons. The data model, evidence model, graph model, API surface, and ingest concept are all coherent.

What is not ready for full-scale deployment is the last mile:

* the ingestion pipeline has a few correctness breaks that will undermine trust at scale
* the “chat” layer is not yet a real tutor; it is an evidence-pack API with a chat-shaped wrapper
* the system still returns **relevant objects**, when your mission needs it to return **implementation paths for ordinary people**

The key shift is this:

**Move from retrieval of documents to composition of action plans.**

## Gap analysis

### 1) Ingestion pipeline: strongest conceptually, weakest operationally

The current 8-pass flow is a good design. The problem is that several passes are still “shape-complete” rather than deployment-complete.

#### P0 blockers

1. **Page provenance is not really page-preserving.**
   In `src/capability_commons/cli/ingest/parse.py`, `markdown_to_segments()` stamps every segment with `page_start=base_page` and `page_end=base_page`, and `run_parse()` calls it without any real page mapping. That means later citations look page-aware, but they are effectively placeholders.

2. **Draft generation under-validates the object schema.**
   In `src/capability_commons/cli/ingest/draft.py`, the prompt asks for a full canonical object, but the Pydantic model only requires `id`, `slug`, `canonical_title`, and `markdown_body`. So incomplete objects can silently pass.

3. **Citation linking is too loose.**
   In `src/capability_commons/cli/ingest/cite.py`, the pass pulls all segments from the same source, not the object’s extracted segment set, and falls back to the first project source if `source_id` is absent. That is a recipe for false support once you ingest multiple sources.

4. **Canonicalization does not actually produce canonicalized objects.**
   In `src/capability_commons/cli/ingest/canonicalize.py`, merge/split decisions only move old files into `_merged/` / `_split/` and write a log. No merged object is materialized, and no split children are created.

5. **The load path has schema mismatches that likely break real ingestion.**

   * `src/capability_commons/cli/ingest/load.py` writes `lifecycle_state = "PUBLISHED"`, while `LifecycleState` values are lowercase (`published`) in `src/capability_commons/domain/enums.py`.
   * `src/capability_commons/cli/seed.py` does `EdgeType(edge_type_str.upper())`, but edge enum values are lowercase.
   * The same seed loader only maps seed-style edge names from CSV (`REQUIRES`, `NEXT`, etc.), so LLM-generated edge rows like `prerequisite_for` will be skipped.
   * `seed.py` constructs `EvidenceSpan(..., metadata_json=...)`, but the ORM/table for `EvidenceSpan` does not define that field.

6. **Publish/index flow is bypassed on ingest load.**
   `seed_graph()` sets `current_version_id` / `published_at` directly, but the worker only creates retrieval segments and embeddings off `version.published` events. So ingest-loaded content will not automatically get chunked/embedded for vector retrieval.

#### P1 quality gaps

7. **The pipeline is still operator-local, not contributor-scale.**
   It assumes local folders, CLI prompts, and file review. That is workable for one operator; it is weak for many contributors, reviewers, or domain stewards.

8. **There is no formal content QA gate before publish.**
   You need citation precision checks, edge precision checks, safety review for risky topics, and implementation-readiness checks before public answers are allowed to quote the object.

9. **The object model is still too document-like for implementation.**
   To help people actually build solar, water, plumbing, food, and resilience systems, each object needs a consistent “can I do this now?” envelope:

   * smallest viable version
   * tools/materials
   * expected time/cost
   * success checks
   * stop conditions
   * common mistakes
   * renter / low-budget / urban / off-grid variants
   * when to escalate to a pro

### 2) Chat/retrieval interface: promising, but not yet a tutor

The intended UX in `docs/plans/WEBSITE_SCAFFOLD.md` is good: intent-aware, context-aware, citations sidebar, contradiction warnings, follow-up. The backend does not yet deliver that contract.

#### P0 blockers

1. **The retrieval API is not really “chat.”**
   `POST /v1/retrieve/evidence_pack` returns an evidence pack and a markdown rendering of ranked evidence. It does not synthesize a direct answer, implementation plan, or personalized next step.

2. **Retrieval uses lexical search only.**
   In `src/capability_commons/retrieval/service.py`, `execute_plan()` calls `self.search.search(...)`, not `search_hybrid(...)`. So the chat/tutor path is losing embeddings even when the search endpoint can use them.

3. **Hybrid search itself is recall-limited.**
   In `src/capability_commons/search/adapters/postgres_search.py`, the “hybrid” flow only rescored FTS hits with vector similarity. If FTS misses, vector never rescues recall. That is not real hybrid retrieval.

4. **Graph expansion is computed but not used.**
   `RetrievalService.execute_plan()` expands neighbors, logs them, and then reranks only the original hits. So the intent-aware graph planner is more observability than actual relevance logic.

5. **Intent is required from the client.**
   The UI spec says intent selection should be optional with a natural-language default. The API currently requires `intent` in `RetrievalRequest`. That is not “usable by anyone.”

6. **Search/ask are not actually public-facing yet.**
   `search` and `retrieve_evidence_pack` both depend on `CurrentWorkspace`, and `get_current_workspace()` requires either a bearer key or an `X-Workspace-Id` header. That blocks anonymous public usage.

#### P1 product gaps

7. **No conversation memory or follow-up state.**
   There is no `conversation_id`, no persistent user context, and no retrieval state for multi-turn narrowing.

8. **No answer contract tuned for implementation.**
   For this domain, the assistant should not just say “here are relevant objects.” It should answer:

   * what to do first
   * what to gather
   * what can go wrong
   * what version fits my context
   * what to learn next

9. **The filter model is weaker than the intended UX.**
   The planned UI wants stage, difficulty, beginner-safe, etc. The current search request mostly supports facets plus object type, so the “ordinary person” controls are thinner than planned.

10. **Search is English-centric.**
    Public usability improves a lot if lexical search is forgiving, accent-insensitive, and eventually multilingual.

## What I would change in the architecture

### Ingestion lane

Keep the current conceptual passes, but change the operating model:

**Source registry → parse store → provenance segments → extraction candidates → canonical drafts → citation linker → QA/review queue → publish → retrieval indexing**

The crucial distinction is between two chunk types:

* **Provenance segments:** exact, page-anchored, reviewer-facing
* **Retrieval chunks:** smaller overlapping chunks optimized for search/answering

Right now those are too entangled.

The other big change: move from “filesystem as workflow engine” to “filesystem as export artifact.”
Use Postgres tables for ingest jobs, artifacts, review tasks, and QA status. Still export YAML for openness and version control, but do not make local folders the primary orchestration layer.

### Answer lane

The public assistant should be:

**Query → context capture → intent inference → hybrid retrieval → graph expansion → answer synthesis → action plan → citations → save/print/teach-forward**

And the answer object should look more like this:

```json
{
  "answer": "Plain-language direct answer",
  "intent": "how_to",
  "context_used": {
    "housing_type": "renter",
    "budget": "low",
    "climate": "humid_subtropical",
    "experience": "beginner"
  },
  "action_now": [
    "Smallest viable next step"
  ],
  "implementation_plan": [
    {
      "step": 1,
      "title": "Do this first",
      "why": "Reason",
      "materials": ["..."],
      "success_check": "..."
    }
  ],
  "safety": {
    "stop_conditions": ["..."],
    "when_to_get_help": ["..."]
  },
  "recommended_objects": [
    {"slug": "...", "role": "prerequisite"}
  ],
  "citations": [
    {"source_title": "...", "excerpt": "..."}
  ],
  "gaps_or_uncertainties": [
    "What the system still does not know"
  ]
}
```

That is the contract I would design the UI around.

## Product recommendation: do not make chat the only entry point

For ordinary people, a blank chat box is weak.

The better public surface is:

1. **Problem-first search**
   “No running water,” “keeping food cold in outage,” “small solar for lights and phone,” “starting a low-cost garden.”

2. **Guided ask**

   * what are you trying to do?
   * what is your situation?
   * how much time/money do you have?
   * do you want overview / step-by-step / troubleshooting / compare / safety?

3. **Action card output**

   * do this now
   * do this next
   * here’s the full plan
   * here’s what you need
   * here’s what can go wrong
   * here’s what to print/save

4. **Deep object pages**
   For people who want the full structured guide, evidence, contradictions, and teach-forward bundle.

Chat should be a layer over structured capability objects, not the whole product.

## 90-day action plan

### Days 0–14: make ingestion trustworthy

* Fix enum casing and edge-type parsing in `load.py` / `seed.py`
* Fix `EvidenceSpan` load mismatch
* Make parse output truly page-anchored
* Restrict citation linking to extracted segment IDs plus small neighbor context
* Make draft validation enforce the full canonical object schema
* Run one real source end-to-end and manually review 100% of the output
* Add a publish path that also reindexes retrieval chunks and embeddings

### Days 15–45: make retrieval actually useful

* Switch `RetrievalService` to real hybrid retrieval
* Change hybrid search to union lexical + vector candidates, then fuse/rerank
* Feed graph-expanded candidates into final ranking
* Add intent auto-detection
* Add context profile capture
* Add structured answer synthesis, not just evidence-pack rendering
* Add a gold query set for evaluation:

  * “I need drinking water if the power is out”
  * “Starter solar for lights and phone”
  * “Renter-safe food resilience”
  * “Why is my rain barrel system not flowing?”
  * “What should I learn before off-grid refrigeration?”

### Days 46–75: make it usable by anyone

* Add a public query proxy or anonymous workspace model
* Build the guided ask flow
* Add “do now / plan / debug / compare / safety” modes
* Add printable action cards and offline-friendly bundles
* Add contradiction and uncertainty display in answers
* Add “beginner-safe only” toggle

### Days 76–90: make it operational

* DB-backed ingest jobs and review tasks
* Citation QA dashboard
* Safety review queue for high-risk topics
* Query analytics and answer-quality metrics
* Add second and third source domains to prove generalization
* Cache popular public queries by normalized query + context

## Metrics that matter

Do not measure only retrieval relevance. Measure implementation usefulness.

Track:

* time to first actionable answer
* citation precision on spot checks
* % of answers with at least 2 grounded citations
* % of sessions that end with a saved/printed action card
* completion rate of “smallest viable next step”
* follow-up rate after first answer
* field report / feedback submission rate
* contradiction exposure rate on disputed topics

## Tech choices I’d keep

I would stay Postgres-first for now. PostgreSQL’s `websearch_to_tsquery` is still a good forgiving lexical front door, and the `unaccent` dictionary is a straightforward way to make search accent-insensitive. pgvector supports both IVFFlat and HNSW; HNSW generally offers the better speed/recall tradeoff, while pgvector-python already includes hybrid-search examples using reciprocal rank fusion. For the LLM passes, Structured Outputs is a better fit than manual JSON parsing and retrying, and OpenAI embeddings remain flexible since `text-embedding-3-small` defaults to 1536 dimensions and supports shortening via the `dimensions` parameter. ([PostgreSQL][1])

My strongest recommendation is this: **treat “implementation-ready answer generation” as a first-class product layer, not as a thin UI over retrieved objects.** That is the step that turns the commons from a knowledge graph into a capability engine.

I can turn this into a prioritized engineering backlog with concrete tickets by file if you want.

[1]: https://www.postgresql.org/docs/current/textsearch-controls.html "https://www.postgresql.org/docs/current/textsearch-controls.html"

