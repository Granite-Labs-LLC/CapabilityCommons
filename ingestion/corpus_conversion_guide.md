# Capability Commons Corpus Conversion Guide

This guide describes how to turn source documents (PDFs, manuals, field notes, transcripts) into **content-backed Capability Commons objects** rather than mere references.

It is designed to fit the current Capability Commons architecture:
- canonical object text lives in `context_object_versions`
- provenance lives in `evidence_sources` and `evidence_spans`
- relationships live in `edges`
- search/retrieval operate over published objects and their segments

---

## 1. Core principle

The pipeline should not do:

`PDF -> chunks -> chatbot answer`

It should do:

`PDF -> parsed sections -> extraction matrix -> canonical content objects -> evidence spans -> edges -> published bundles -> chatbot retrieval`

The content object is the primary public unit. The source document is the supporting evidence.

---

## 2. Output artifacts

For each source corpus, produce four machine-readable outputs:

1. `extraction_matrix.csv`
2. `objects/*.yaml`
3. `edges.csv`
4. `evidence_map.json`

Optional:
5. `review_queue.json`
6. `bundle_overrides/*.yaml`
7. `source_manifest.yaml`

---

## 3. Recommended pipeline

### Pass 0 — source normalization

Input: PDF / DOCX / HTML / scans

Tasks:
- convert to text or markdown while preserving:
  - page number
  - heading structure
  - tables
  - figures / captions
  - character offsets if possible
- create one `evidence_source` record per document
- split into `source_segments.jsonl`

Recommended segment record:

```json
{
  "source_id": "src.permatil.refbook.2006",
  "segment_id": "seg_000341",
  "page_start": 111,
  "page_end": 111,
  "heading_path": ["Module 5", "Community Seed Saving Group"],
  "text": "...",
  "start_char": 0,
  "end_char": 1432,
  "figure_refs": [],
  "table_refs": []
}
```

Rules:
- do not lose page boundaries
- do not merge unrelated headings into one segment
- keep tables as structured markdown or CSV sidecars when possible
- keep figures/captions linked to nearby text

---

### Pass 1 — extraction matrix generation

Goal: map source sections to candidate Capability Commons objects before drafting full text.

The LLM reads one section or a small cluster of related sections and emits rows describing:
- what capability is present
- what type it should become
- whether it should be merged with nearby material
- which claims are descriptive vs procedural vs cautionary

#### Extraction matrix columns

```csv
source_id,section_id,start_page,end_page,heading_path,segment_ids,candidate_slug,candidate_type,primary_domain,secondary_domains,stage,contexts,summary,key_concepts,key_actions,tools_materials,failure_modes,safety_boundaries,local_adaptation_signals,needs_split,needs_merge,confidence
```

#### Example row

```csv
src.permatil.refbook.2006,sec_5_community_seed_group,111,114,"Module 5 > Community Seed Saving Group","seg_341|seg_342|seg_343","food.seed-saving.community-group",project_blueprint,food,"community;gardens",productive,"rural;urban;low_budget","Shared local system for collecting, drying, storing, testing, exchanging and distributing seed","seed diversity;community stock;selection;drying;storage","organize exchange;select parent plants;collect and dry;test viability;package seed","storage containers;labels;drying space;record sheets","poor drying; insect contamination; poor labeling; bad germination","must avoid diseased seed; verify germination before trading","highly local crop varieties and timing",false,false,0.91
```

#### Pass 1 prompt template

```text
SYSTEM
You are an extraction analyst for Capability Commons.
Your job is not to summarize the whole book. Your job is to identify reproducible capabilities,
practical concepts, projects, exercises, assessments, and adaptations.

You must output ONLY valid CSV rows or valid JSON objects matching the requested schema.
Do not write prose outside the schema.
Do not invent page numbers, sections, or claims.
Mark uncertainty explicitly.
Do not copy long passages from the source.

USER
Project doctrine:
- The unit of value is the reproducible capability.
- Capability Commons maps concepts -> skills -> projects -> local deployment -> teach-forward.
- Preferred object types: concept_note, skill_guide, project_blueprint, reference_sheet,
  module, assessment, learning_path, field_report, local_adaptation, teach_forward_packet.

For each provided section:
1. identify candidate objects
2. classify type
3. decide split vs merge
4. list key concepts, key actions, tools, risks, local adaptation signals
5. propose a canonical slug
6. include source page range and segment IDs

Return JSON array using this schema:
{...}

SOURCE SECTION:
{{section_text}}
```

---

### Pass 2 — canonical object drafting

Goal: convert extraction matrix rows into fully written, learner-facing objects.

Each drafted object should be:
- paraphrased and synthesized
- beginner-readable
- structured for search and retrieval
- explicitly linked to supporting spans
- practical, not merely descriptive

#### Object drafting rules

1. One object = one coherent capability or one coherent principle.
2. If a section contains both theory and an independent task, emit **two objects**:
   - `concept_note`
   - `skill_guide` or `project_blueprint`
3. If the section is a workshop exercise, consider:
   - `module`
   - `assessment`
   - `teach_forward_packet`
4. If the advice is highly local or contingent, emit `local_adaptation` rather than treating it as universal canon.
5. If the text expresses a distinctive school of thought rather than settled practice, attach it as:
   - `alternative_to`
   - `derived_from`
   - `supported_by`
   rather than presenting it as the only valid path.
6. Avoid long quotation. Use short evidence excerpts only in citation metadata.

#### Draft object schema (ingestion-friendly YAML)

```yaml
id: food.seed-saving.community-group
seed_type: project
co_type: PROJECT_BLUEPRINT
slug: food.seed-saving.community-group
canonical_title: "Start a Community Seed Saving Group"
version_no: 1
lifecycle_state: DRAFT
visibility: public
language_code: en
primary_domain: food
secondary_domains: [community, gardens]
stage: productive
contexts: [rural, urban, low_budget, off_grid]
difficulty: 2
cost_band: low
risk_band: low
summary_short: "Build a shared local system for collecting, drying, storing, testing, and exchanging seed."
summary_medium: "A community seed saving group pools labor and storage so members can maintain better seed quality, preserve local varieties, and reduce dependence on outside suppliers."
plain_language: "Instead of each household trying to save every seed alone, a group can share the work. One group can select good parent plants, dry seed correctly, test it, label it, and keep it ready for planting or exchange."
markdown_body: |
  ## What this is
  A community seed saving group is a shared local system for keeping good seed in circulation.

  ## Why it matters
  Shared seed work can increase diversity, improve seed quality, and reduce repeated labor.

  ## Core workflow
  1. Choose healthy parent plants.
  2. Collect seed at the right maturity.
  3. Clean and dry the seed thoroughly.
  4. Label and store it in protected containers.
  5. Test germination before exchange or sale.
  6. Keep records of source, timing, and performance.

  ## Common failure modes
  - Seed stored with too much moisture
  - Poor labeling or mixed varieties
  - Saving seed from weak or diseased plants
  - Trading untested seed

  ## Local adaptation notes
  Drying methods, storage containers, crop calendars, and exchange norms should be adapted to local humidity, pests, and crop types.
structured_data:
  goal: "Create a functioning community seed-saving workflow."
  deliverables:
    - "Seed and planting material list"
    - "Labeled seed stock"
    - "Simple germination test log"
    - "Exchange or distribution plan"
  acceptance_criteria:
    - "Stored seed is labeled and traceable"
    - "At least one viability test completed"
    - "Selection and storage rules documented"
    - "Roles for collection, drying, storage, and exchange assigned"
  time_box_hours: 8
  budget_band: low
  team_size: 5
requires:
  - food.seed-selection-basics
  - food.seed-drying-basics
  - food.seed-storage-basics
suggested_edges:
  - target_id: food.seed-selection-basics
    edge_type: builds_on
  - target_id: food.seed-viability-testing
    edge_type: contains
  - target_id: community.local-exchange-networks
    edge_type: next_step_for
citations:
  - claim_id: clm_001
    supports: "Shared groups can increase seed variety and make saving and distribution easier."
    source_id: src.permatil.refbook.2006
    page_start: 111
    page_end: 111
    segment_id: seg_000341
    excerpt: "community seed saving group"
    start_char: 0
    end_char: 28
  - claim_id: clm_002
    supports: "Members should select healthy, disease-resistant plants and manage collection, drying, and storage."
    source_id: src.permatil.refbook.2006
    page_start: 111
    page_end: 114
    segment_id: seg_000342
    excerpt: "seed selection"
    start_char: 290
    end_char: 304
review_notes:
  - "Check whether viability testing deserves a separate skill_guide object."
```

---

### Pass 3 — citation and evidence-span attachment

This pass is critical.

The LLM should not just draft text. It must produce **claim-to-span links**.

#### Citation rules

- Every non-trivial procedural claim needs at least one source span.
- Every caution or safety claim needs at least one source span.
- If a paragraph makes 3 different claims, split them into 3 `claim_id`s.
- If the source only weakly supports a claim, mark `support_strength: weak`.
- If multiple sources support the same claim, attach them all.
- If the object synthesizes across sources, cite each contributing source.

#### Evidence map schema

```json
[
  {
    "object_id": "food.seed-saving.community-group",
    "claim_id": "clm_001",
    "claim_text": "A seed-saving group can increase variety and reduce duplicated labor.",
    "support": [
      {
        "source_id": "src.permatil.refbook.2006",
        "page_start": 111,
        "page_end": 111,
        "segment_id": "seg_000341",
        "excerpt": "share excess seeds and increase seed variety",
        "start_char": 32,
        "end_char": 73,
        "support_strength": "strong"
      }
    ]
  }
]
```

#### Citation-linking prompt template

```text
SYSTEM
You are a citation linker.
For each drafted claim, attach one or more supporting source spans.
Do not invent citations.
If support is partial, say so.
If no support exists, return NO_SUPPORT.
Output only valid JSON.

USER
Object draft:
{{draft_object}}

Available source segments:
{{segments_with_pages_and_offsets}}
```

---

### Pass 4 — canonicalization and deduplication

By now you will have many overlapping drafts.

Goal:
- merge duplicates
- split overloaded objects
- select canonical slug/title
- preserve source diversity

#### Canonicalization heuristics

Merge when:
- same learner outcome
- same action chain
- same prerequisites and constraints
- text differs only stylistically

Split when:
- one object contains multiple distinct tasks
- concept explanation and execution steps are both long
- local adaptation materially changes the procedure
- safety boundaries differ by context

#### Canonicalization prompt template

```text
SYSTEM
You are a corpus editor.
Merge duplicates and split overloaded drafts while preserving provenance.
Choose one canonical slug.
Do not discard source support.
Return JSON with: action=merge|split|keep, rationale, canonical_object, deprecated_draft_ids.

USER
Draft set:
{{drafts}}
```

---

### Pass 5 — edge extraction

Now derive graph structure.

Edges should be generated from the object set, not from raw PDFs directly.

#### Edge extraction targets

- `prerequisite_for`
- `builds_on`
- `next_step_for`
- `contains`
- `assessed_by`
- `supported_by`
- `derived_from`
- `alternative_to`
- `adapted_for`
- `applies_in`
- `requires_tool`
- `requires_material`
- `has_failure_mode`
- `mitigated_by`
- `unsafe_without`
- `bounded_by`
- `corrected_by`
- `contradicted_by`
- `supersedes`

#### Edge generation rules

- `prerequisite_for` if object B cannot be executed or understood safely without object A.
- `builds_on` if object B benefits from A but does not strictly require it.
- `contains` if a blueprint/module/packet includes smaller objects as sub-steps.
- `alternative_to` if two objects solve the same problem by materially different approaches.
- `adapted_for` if an object is a region / budget / climate / settlement variant.
- `has_failure_mode` should point to a `reference_sheet`, `correction`, or `field_report` object describing the failure.
- `bounded_by` should point to objects describing constraints, not vague notes.

#### Edge CSV

```csv
source_id,target_id,edge_type,sequence,condition,confidence
food.seed-saving.community-group,food.seed-selection-basics,builds_on,,,
food.seed-saving.community-group,food.seed-drying-basics,contains,1,,0.92
food.seed-saving.community-group,food.seed-storage-basics,contains,2,,0.91
food.seed-saving.community-group,food.seed-viability-testing,contains,3,,0.95
food.seed-saving.community-group,community.local-exchange-networks,next_step_for,,"after stock + testing workflow exists",0.77
```

---

### Pass 6 — bundle conversion

Every core topic should render to the five/six public formats.

Generate:
- `hook`
- `primer`
- `guide`
- `reference`
- `worksheet`
- `teach_forward_kit`

#### Bundle generation prompt

```text
SYSTEM
You are a curriculum converter.
Turn the canonical object into a six-part public bundle.
Keep it practical, plain-language, and beginner-safe.
Do not introduce claims not supported by the draft object.
Return JSON only.

USER
Canonical object:
{{object_yaml_or_json}}
```

#### Bundle JSON schema

```json
{
  "object_id": "food.seed-saving.community-group",
  "hook": "Why save seed as a group instead of alone?",
  "primer": "...",
  "guide": "...",
  "reference": ["..."],
  "worksheet": ["..."],
  "teach_forward_kit": {
    "three_minute_version": "...",
    "ten_minute_outline": ["..."],
    "discussion_prompts": ["..."]
  }
}
```

---

### Pass 7 — review and publication

Before publication, run automated and human checks.

#### Automated checks

- schema valid
- slug valid and unique
- required fields present
- every non-trivial claim has citation coverage
- no orphan citations
- no duplicate objects with >0.92 similarity
- no long copyrighted text copied into `markdown_body`
- required `structured_data` fields present for object type
- `risk_band` set when failure modes or hazards exist
- at least one of `requires`, `suggested_edges`, or citations exists

#### Human review queue

Review for:
- correctness
- readability
- practical utility
- safe boundaries
- locality assumptions
- overstatement / ideology drift
- whether object should really be canonical vs local adaptation

Lifecycle:
- `DRAFT`
- `IN_REVIEW`
- `REVIEWED`
- `VERIFIED`
- `PUBLISHED`

---

## 4. Split/merge rules for common source patterns

### A. textbook chapter
Often becomes:
- 1 concept_note
- 1 skill_guide
- 1 reference_sheet
- maybe 1 project_blueprint

### B. workshop lesson-plan page
Often becomes:
- 1 module
- 1 assessment
- 1 teach_forward_packet
- several linked skill_guides

### C. table / checklist
Often becomes:
- reference_sheet
- worksheet
- assessment rubric

### D. school-of-thought or philosophy text
Often becomes:
- concept_note
- alternative_to edges to more conventional techniques
- maybe correction or contradiction cases if conflicts arise later

### E. locality-specific advice
Often becomes:
- local_adaptation
- contexts/facets
- adapted_for / applies_in edges

---

## 5. Recommended object-writing style guide

### Do
- paraphrase the source into plain language
- state what the learner can do after reading
- include action steps and failure modes
- keep each object narrow enough to retrieve cleanly
- attach every significant claim to evidence
- separate universal guidance from local adaptation

### Do not
- dump chapter summaries into one giant object
- copy long passages from copyrighted sources
- let the LLM invent tools, quantities, or page numbers
- turn every paragraph into a separate object
- flatten competing schools of thought into one voice

### Good object size
- `concept_note`: 300–900 words
- `skill_guide`: 500–1200 words
- `project_blueprint`: 500–1500 words
- `reference_sheet`: 150–600 words
- `module`: 300–1000 words plus structured fields
- `teach_forward_packet`: compact, handoff-oriented

---

## 6. Recommended LLM orchestration

### Stage A — deterministic preprocessing
Use code, not LLM, for:
- OCR / PDF parsing
- page boundary preservation
- heading detection where reliable
- figure/table extraction where possible
- text chunking
- dedupe by exact text hash

### Stage B — LLM extraction matrix
Small context windows, section-by-section.

### Stage C — LLM draft generation
Clustered by candidate object.

### Stage D — LLM citation linking
Claims back to source spans.

### Stage E — deterministic validation
Schema, coverage, duplication, missing fields.

### Stage F — LLM editorial pass
Tone, clarity, bundle generation, teach-forward conversion.

### Stage G — human review
Canon decision.

---

## 7. Pseudocode

```python
for source_doc in source_docs:
    source = register_evidence_source(source_doc)
    segments = parse_and_segment(source_doc, preserve_pages=True)
    save_segments(source.id, segments)

    extraction_rows = []
    for section in group_into_sections(segments):
        extraction_rows += llm_generate_extraction_matrix(section)

    candidate_clusters = cluster_rows_into_candidate_objects(extraction_rows)

    drafts = []
    for cluster in candidate_clusters:
        draft_objects = llm_draft_objects(cluster, fetch_segments(cluster.segment_ids))
        for draft in draft_objects:
            draft.citations = llm_link_claims_to_spans(draft, fetch_segments(cluster.segment_ids))
            validate_schema(draft)
            validate_citation_coverage(draft)
            drafts.append(draft)

canonical_drafts = canonicalize_and_dedupe(drafts)
edges = llm_extract_edges(canonical_drafts)
bundles = [llm_generate_bundle(obj) for obj in canonical_drafts if is_core_topic(obj)]

for obj in canonical_drafts:
    save_context_object(obj)
for edge in edges:
    save_edge(edge)
for bundle in bundles:
    save_bundle(bundle)

queue_for_review(canonical_drafts)
publish_reviewed_objects()
```

---

## 8. Minimal schemas

### `source_manifest.yaml`

```yaml
source_id: src.permatil.refbook.2006
source_title: "Permaculture Reference Book"
source_kind: BOOK
language_code: en
license_status: unknown
ingested_from: "Permaculture_Reference_Book.pdf"
authority_tier: secondary
notes:
  - "Community-oriented practical permaculture curriculum"
```

### `review_queue.json`

```json
[
  {
    "object_id": "food.seed-saving.community-group",
    "checks": {
      "schema_valid": true,
      "citation_coverage": 0.92,
      "duplicate_risk": 0.14,
      "copyright_copy_ratio": 0.06,
      "safety_review_required": false
    },
    "review_recommendation": "promote_to_in_review"
  }
]
```

---

## 9. Example: extraction matrix -> object -> edges

### Source section
- Module 5: Seed Saving & Nurseries
- Community Seed Saving Group
- Seed Collection & Storage exercise
- Seed viability testing exercise

### Candidate objects
1. `food.seed-saving.community-group` — `project_blueprint`
2. `food.seed-selection-basics` — `skill_guide`
3. `food.seed-drying-basics` — `skill_guide`
4. `food.seed-storage-basics` — `skill_guide`
5. `food.seed-viability-testing` — `skill_guide`
6. `community.seed-exchange-basics` — `concept_note`
7. `module.seed-saving-and-nurseries` — `module`
8. `assessment.seed-saving-practical` — `assessment`
9. `teach-forward.seed-saving-mini-workshop` — `teach_forward_packet`

### Relationships
- community group blueprint `contains` selection, drying, storage, testing
- module `contains` the skill guides and project
- assessment `assessed_by` module / validates skill guides
- teach-forward packet `summarizes` the module and blueprint

---

## 10. Recommended developer implementation notes

### A. Extend seed YAML schema

The current seed example is too metadata-light for a content-backed corpus. Add:
- `summary_medium`
- `summary_long`
- `markdown_body`
- `citations`
- `structured_data`
- `suggested_edges`
- `bundle_overrides` (optional)

### B. Add claim-aware validation

At publication time:
- parse `markdown_body` into claim blocks
- ensure each claim block has at least one citation record
- ensure citations point to valid `source_id/page/segment_id`

### C. Preserve source plurality

If multiple sources cover the same capability:
- merge into one canonical object
- keep all supporting evidence
- add `alternative_to` only when methods really differ

### D. Keep ideology separable from procedure

Example:
- a philosophical argument for natural farming can be a `concept_note`
- a concrete direct-seeding method can be a `skill_guide`
- those should be linked, not collapsed into one blob

---

## 11. Good default model split for farming/permaculture sources

For books like the ones you uploaded, the most reliable object decomposition is:

- chapter intro -> `concept_note`
- task/process section -> `skill_guide`
- integrated build/organization section -> `project_blueprint`
- workshop page -> `module` + `assessment`
- field exercise page -> `teach_forward_packet` or `module` fragment
- warnings, pests, hazards, quarantine, food safety -> `reference_sheet` or `safety_notice`
- local crop lists / seasonal lists -> `reference_sheet` + `local_adaptation`

---

## 12. One-line operating rule

Never ask the LLM to produce “a summary of the PDF.”
Ask it to produce:

- extraction matrix rows
- canonical objects
- citation maps
- edges
- bundles

in separate passes, with schema validation between each pass.
