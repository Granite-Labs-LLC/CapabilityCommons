# Ingestion Tooling — Design Spec

> **Goal:** Build a multi-pass CLI pipeline that converts source documents (PDFs, manuals, field notes) into fully populated Capability Commons knowledge objects — with body text, citations, edges, and bundles — searchable, retrievable, and ready for the public API.

## 1. Problem

The Capability Commons architecture supports rich knowledge objects with versioned content, evidence provenance, typed edges, and curriculum bundles. But the only way to populate it today is the `seed.py` CLI, which loads pre-authored YAML with minimal body text and no citations.

The `ingestion/` directory contains a conversion guide, YAML/CSV templates, and LLM prompt templates describing how source material should be transformed into canonical objects. What's missing is **runnable tooling** that executes this pipeline.

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM provider | OpenAI-compatible abstract client | One `base_url` + `api_key` supports OpenAI, Ollama, vLLM, any compatible provider |
| PDF parsing | `marker-pdf` (ML-based) | Handles scanned, semi-structured PDFs with columns, tables, and mixed layouts |
| Operator model | Separate CLI command per pass | Operator inspects and edits intermediate artifacts between passes; matches the guide's multi-pass philosophy |
| Intermediate storage | `ingestion/projects/<name>/` in the repo | Git-friendly, reviewable, enables community contributions via PR |
| Final output shape | Seed-compatible (`canonical/nodes/*.yaml` + `imports/edges.csv`) | Direct compatibility with existing `seed.py` loader |
| Database loading | Extend `seed.py` to handle richer YAML | One loader, backwards compatible; no code duplication |
| Structured output | Pydantic models with LLM retry on validation failure | Consistent with the rest of the codebase; catches malformed LLM output immediately |
| Scope | All 8 passes (parse, extract, draft, cite, canonicalize, edges, bundles, load) + validate/status utilities | Full pipeline from the corpus conversion guide |
| Default lifecycle | Ingested objects default to `DRAFT`, not `PUBLISHED` | LLM-drafted content needs human review before going live; `--publish` flag overrides |

## 3. Architecture

### 3.1 File Structure

```
src/capability_commons/cli/ingest/
├── __init__.py
├── __main__.py          # argparse dispatch: init, parse, extract, draft, cite,
│                        #   canonicalize, edges, bundles, load, validate, status
├── parse.py             # Pass 0: PDF → markdown segments (deterministic)
├── extract.py           # Pass 1: segments → extraction matrix (LLM)
├── draft.py             # Pass 2: matrix rows → canonical YAML objects (LLM)
├── cite.py              # Pass 3: drafts → citation/evidence linking (LLM)
├── canonicalize.py      # Pass 4: dedup, merge, split (LLM + rapidfuzz)
├── edges.py             # Pass 5: object set → typed edges (LLM)
├── bundles.py           # Pass 6: objects → six-part bundles (LLM)
├── load.py              # Pass 7: validate + load to database (deterministic)
├── llm_client.py        # OpenAI-compatible client with Pydantic retry
├── models.py            # Pydantic models for all intermediate artifacts
└── project.py           # Project directory management + manifest I/O
```

### 3.2 Project Directory Layout

Each ingestion run is a named project:

```
ingestion/projects/<project-name>/
├── manifest.yaml              # Sources, LLM config, pass completion timestamps
├── sources/                   # Original PDFs (or symlinks)
├── segments/                  # Pass 0 output
│   ├── source_manifest.yaml   # Evidence source records
│   └── segments.jsonl         # Page-preserving text segments
├── matrix/                    # Pass 1 output
│   └── extraction_matrix.csv
├── drafts/                    # Pass 2 output (+ edits from passes 3, 4, 6)
│   ├── *.yaml                 # One file per canonical object
│   ├── _merged/               # Pass 4: deprecated merged drafts
│   └── _split/                # Pass 4: deprecated split drafts
├── citations/                 # Pass 3 output
│   └── evidence_map.json
├── edges/                     # Pass 5 output
│   └── edges.csv
├── output/                    # Pass 7: seed-compatible final shape
│   ├── canonical/nodes/*.yaml
│   └── imports/edges.csv
└── logs/                      # Per-pass run logs
```

### 3.3 Manifest Schema

```yaml
name: permaculture-seed-saving
created: 2026-03-23T12:00:00Z
sources:
  - id: src.permatil.refbook.2006
    file: sources/Permaculture_Reference_Book.pdf
    title: "Permaculture Reference Book"
    source_kind: BOOK
llm:
  base_url: https://api.openai.com/v1
  model: gpt-4o
  temperature: 0.2
passes:
  parse: { completed: null }
  extract: { completed: null }
  draft: { completed: null }
  cite: { completed: null }
  canonicalize: { completed: null }
  edges: { completed: null }
  bundles: { completed: null }
  load: { completed: null }
```

## 4. CLI Interface

All commands are invoked via `python -m capability_commons.cli.ingest <command> <project-name>`.

### 4.1 Commands

```bash
# Initialize a new project
ingest init <project-name> \
  --source <path-to-pdf> \
  --source-id <evidence-source-id> \
  --source-title "Title" \
  --source-kind BOOK

# Pass 0: Parse PDFs into segments
ingest parse <project-name>

# Pass 1: Generate extraction matrix
ingest extract <project-name> \
  --sections "Module 5"           # optional: scope to specific headings

# Pass 2: Draft canonical objects
ingest draft <project-name> \
  --skip-existing                  # preserve hand-edited drafts
  --slugs "food.seed-*"           # optional: scope to specific slugs (glob)

# Pass 3: Link citations to source spans
ingest cite <project-name> \
  --slugs "food.seed-*"           # optional: scope to specific slugs

# Pass 4: Canonicalize and deduplicate
ingest canonicalize <project-name>

# Pass 5: Extract edges from object set
ingest edges <project-name>

# Pass 6: Generate six-part bundles
ingest bundles <project-name> \
  --skip-existing                  # preserve hand-edited bundles
  --slugs "food.seed-*"           # optional: scope to specific slugs

# Pass 7: Validate and load to database
ingest load <project-name> \
  --publish                        # override default DRAFT → PUBLISHED
  --dry-run                        # validate only, don't write to DB

# Utilities
ingest validate <project-name>    # check schema, coverage, dupes
ingest status <project-name>      # table of pass completion + file counts
```

### 4.2 Global Flags

All LLM passes accept these overrides (take precedence over `manifest.yaml`):

- `--model <model-name>` — override model
- `--base-url <url>` — override API base URL
- `--api-key <key>` — override API key (also reads `OPENAI_API_KEY` from env)
- `--temperature <float>` — override temperature

## 5. Pass Implementations

### 5.0 Parse (`parse.py`)

**Input:** PDFs listed in `manifest.yaml`
**Output:** `segments/segments.jsonl`, `segments/source_manifest.yaml`
**LLM:** No — fully deterministic.

- Runs `marker` to convert each PDF to markdown with page boundaries.
- Splits markdown into segments at heading boundaries, preserving `page_start`, `page_end`, `heading_path`.
- Assigns sequential `segment_id`s (`seg_000001`, `seg_000002`, ...).
- Computes `start_char` / `end_char` offsets within the source.
- Writes one `SourceSegment` per line to JSONL.
- Writes evidence source records to `source_manifest.yaml`.
- On first run, notes that marker model download (~500MB) may take time.

### 5.1 Extract (`extract.py`)

**Input:** `segments/segments.jsonl`
**Output:** `matrix/extraction_matrix.csv`
**LLM:** Yes — extraction matrix prompt.

- Groups segments into sections by heading structure (configurable depth, default: top 2 levels).
- Optional `--sections` filter scopes to matching headings.
- For each section, sends segment text to LLM → `list[ExtractionRow]`.
- Prints token estimate and cost confirmation before proceeding.
- Writes all rows to CSV via polars.

### 5.2 Draft (`draft.py`)

**Input:** `matrix/extraction_matrix.csv`, `segments/segments.jsonl`
**Output:** `drafts/<slug>.yaml` (one per object)
**LLM:** Yes — object drafting prompt.

- Reads matrix rows. Clusters rows marked `needs_merge`.
- For each row/cluster, fetches referenced segments.
- Sends matrix row + segments to LLM → YAML object matching `content_object_template.yaml`.
- `--skip-existing` preserves hand-edited drafts, only generates missing slugs.
- Prints token estimate and cost confirmation.

### 5.3 Cite (`cite.py`)

**Input:** `drafts/*.yaml`, `segments/segments.jsonl`
**Output:** `citations/evidence_map.json` + patched `citations` fields in draft YAML
**LLM:** Yes — citation linking prompt.

- For each draft, extracts substantive claims from `markdown_body`.
- Sends draft + referenced segments to LLM → `list[ClaimCitation]`.
- Writes full evidence map to JSON.
- Patches the `citations` field in each draft YAML so drafts become self-contained.

### 5.4 Canonicalize (`canonicalize.py`)

**Input:** `drafts/*.yaml`
**Output:** Updated `drafts/*.yaml`, deprecated files in `_merged/`/`_split/`, `drafts/canonicalization_log.json`
**LLM:** Yes — canonicalization prompt. **Also uses:** `rapidfuzz` for pre-LLM similarity grouping.

- Groups drafts by domain + `rapidfuzz` title/summary similarity.
- For each group with similarity above threshold, sends to LLM → `keep | merge | split` decision.
- Merges: writes canonical object, moves deprecated drafts to `_merged/`.
- Splits: writes new objects, moves original to `_split/`.
- Logs all decisions with rationale to `canonicalization_log.json`.

### 5.5 Edges (`edges.py`)

**Input:** `drafts/*.yaml`
**Output:** `edges/edges.csv`
**LLM:** Yes — edge extraction prompt.

- Collects all object summaries (slug, type, title, summary, requires, suggested_edges).
- Sends full set to LLM → `list[ExtractedEdge]`.
- Merges with `suggested_edges` already in draft YAML (dedup by source+target+type).
- Writes edges CSV via polars.

### 5.6 Bundles (`bundles.py`)

**Input:** `drafts/*.yaml`
**Output:** Updated `bundle_overrides` in draft YAML
**LLM:** Yes — bundle generation prompt.

- Filters to core topic types: `skill_guide`, `project_blueprint`, `module`.
- For each, sends to LLM → six-part bundle (hook, primer, guide, reference, worksheet, teach_forward_kit).
- Writes `bundle_overrides` into each draft YAML.
- `--skip-existing` preserves hand-edited bundles.

### 5.7 Load (`load.py`)

**Input:** `drafts/*.yaml`, `edges/edges.csv`
**Output:** Database records + `output/` seed-compatible directory
**LLM:** No — deterministic.

- Validates all drafts against database schema (required fields, valid enums, slug uniqueness).
- Validates citation coverage (warns if objects have no citations).
- Writes `output/canonical/nodes/*.yaml` + `output/imports/edges.csv` in seed-compatible shape.
- Extends `seed.py` to handle richer fields (see §6).
- Default lifecycle: `DRAFT`. `--publish` flag sets `PUBLISHED`.
- `--dry-run` validates and writes `output/` without touching the database.
- Idempotent by slug — existing objects are skipped.

## 6. Extending seed.py

The `load` step extends `seed.py` to handle fields from the ingestion YAML. All changes are backwards compatible — existing seed packs work unchanged.

| Field | Current behavior | New behavior |
|-------|-----------------|-------------|
| `markdown_body` | Falls back to `summary` | Use `markdown_body` if present, else `summary` |
| `summary_medium` | Ignored | Write to `ContextObjectVersion.summary_medium` if present |
| `structured_data` | Built from `payload` | Also merge top-level `structured_data` if present |
| `citations` | Not handled | For each: find-or-create `EvidenceSource` by `source_id`, create `EvidenceSpan` with page/char offsets, link to version |
| `suggested_edges` | Not handled | Append to edge set alongside `requires` + CSV edges, same dedup logic |
| `bundle_overrides` | Not handled | Store in `structured_data` under `_bundle` key |
| `review_notes` | Not handled | Log as warnings, don't store |
| `lifecycle_state` | Always `PUBLISHED` | Read from YAML, default `DRAFT` for ingested content; `--publish` overrides |
| `summary_long` | Ignored | Store in `structured_data` under `summary_long` key (no dedicated DB column) |
| `requires` (flat list) | Only handles grouped format `{mode, ids}` | Accept both formats: flat list of slug strings and grouped `{mode, ids}` dicts |
| `co_type` | Not present (uses `type` + mapping) | Check `co_type` first (direct enum value e.g. `PROJECT_BLUEPRINT`), fall back to `type` (mapped via `SEED_TYPE_TO_CO_TYPE`) |
| `confidence` (edges CSV) | Hardcoded to `1.0` | Read `confidence` column from CSV when present, default `1.0` when absent |
| `suggested_edges` | Not handled | Normalize each `{target_id, edge_type}` dict into the same edge format, using the object's own slug as `source_id`, default confidence `0.8` |

### 6.1 Evidence Source/Span ID Mapping

The ingestion pipeline uses string source IDs like `src.permatil.refbook.2006` and string segment IDs like `seg_000341`. The database uses UUID primary keys.

**Evidence sources:** Add a new `external_id` column (unique, nullable string) to `evidence_sources` via an Alembic migration. The `load` step does find-or-create by `external_id`. This allows ingestion YAML to reference sources by stable human-readable IDs across multiple project directories.

**Evidence spans:** Ingestion segment IDs (`seg_000341`) are provenance references, not the same as `content_segments` (which are generated by the search indexer when objects are published). The `load` step stores the ingestion `segment_id` in `EvidenceSpan.metadata_json` alongside page/char offsets. The `EvidenceSpan.segment_id` FK to `content_segments` remains nullable — it only gets populated after the object is published and the indexer creates content segments.

### 6.2 Required Alembic Migration

A new migration adds:
- `evidence_sources.external_id` — `VARCHAR(255)`, unique, nullable, indexed
- This is the only schema change required for the ingestion tooling

## 7. Pydantic Models

All intermediate artifacts are typed. Defined in `models.py`:

```python
class SourceSegment(BaseModel):
    source_id: str
    segment_id: str
    page_start: int
    page_end: int
    heading_path: list[str]
    text: str
    start_char: int
    end_char: int
    figure_refs: list[str] = []
    table_refs: list[str] = []

class ExtractionRow(BaseModel):
    source_id: str
    section_id: str
    start_page: int
    end_page: int
    heading_path: str
    segment_ids: list[str]
    candidate_slug: str
    candidate_type: Literal[
        "concept_note", "skill_guide", "project_blueprint", "module", "assessment",
        "reference_sheet", "learning_path", "teach_forward_packet", "local_adaptation",
        "field_report", "worksheet", "glossary", "safety_notice", "correction",
    ]
    primary_domain: str
    secondary_domains: list[str] = []
    stage: str
    contexts: list[str] = []
    summary: str
    key_concepts: list[str] = []
    key_actions: list[str] = []
    tools_materials: list[str] = []
    failure_modes: list[str] = []
    safety_boundaries: list[str] = []
    local_adaptation_signals: list[str] = []
    needs_split: bool = False
    needs_merge: bool = False
    confidence: float

class CitationSpan(BaseModel):
    source_id: str
    page_start: int
    page_end: int
    segment_id: str
    excerpt: str
    start_char: int
    end_char: int
    support_strength: Literal["strong", "medium", "weak"]

class ClaimCitation(BaseModel):
    object_id: str
    claim_id: str
    claim_text: str
    support: list[CitationSpan]

class ExtractedEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    sequence: int | None = None
    condition: str | None = None
    confidence: float

class CanonicalizationDecision(BaseModel):
    action: Literal["keep", "merge", "split"]
    rationale: str
    canonical_slug: str
    deprecated_draft_ids: list[str] = []

class ValidationReport(BaseModel):
    objects_count: int
    edges_count: int
    citations_count: int
    errors: list[str]
    warnings: list[str]
    citation_coverage: float
```

## 8. LLM Client

### 8.1 Interface

```python
class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.2):
        ...

    async def generate(
        self,
        system: str,
        user: str,
        response_model: type[BaseModel],
        max_retries: int = 3,
    ) -> BaseModel:
        ...
```

### 8.2 Retry Behavior

1. Send system + user message requesting JSON output.
2. Parse response as JSON.
3. Validate against `response_model`.
4. On validation failure: append assistant response + user error message to conversation, retry.
5. After `max_retries` failures: raise `LLMValidationError` with last response and error.

### 8.3 Configuration

- Reads from `manifest.yaml` (`llm.base_url`, `llm.model`, `llm.temperature`).
- CLI flags `--model`, `--base-url`, `--api-key`, `--temperature` override manifest.
- `OPENAI_API_KEY` environment variable used if no key provided.

### 8.4 Cost Estimation

Before each LLM pass, estimate total tokens using `tiktoken`:
```
Pass 2: 47 sections, ~85k input tokens, ~$0.12 at gpt-4o pricing. Proceed? [y/N]
```

Estimation is best-effort (tiktoken may not have encodings for all providers). Skip confirmation with `--yes` flag.

## 9. Error Handling and Resumability

### 9.1 Re-run Behavior

| Pass | Re-run strategy |
|------|----------------|
| `parse` | Overwrites `segments/` (deterministic) |
| `extract` | Overwrites `matrix/`; with `--sections` filter, only regenerates matching rows |
| `draft` | Overwrites `drafts/<slug>.yaml`; `--skip-existing` preserves hand-edited files |
| `cite` | Overwrites `citations/evidence_map.json` and patches draft YAML |
| `canonicalize` | Restores `_merged/`/`_split/` files, then reruns decisions |
| `edges` | Overwrites `edges/edges.csv` |
| `bundles` | Overwrites `bundle_overrides` in drafts; `--skip-existing` preserves edits |
| `load` | Idempotent by slug (existing objects skipped) |

### 9.2 Interruption Safety

No database state is touched until `load`. Partial output files on disk are overwritten on next run.

### 9.3 LLM Failure Handling

If an LLM call fails after all retries, the pass logs the error, skips that section/object, and continues. Summary of successes/failures printed at the end. Operator can re-run with `--sections` or `--slugs` to retry just the failures.

### 9.4 Validation Checks

The `validate` command checks:
- Schema validity of all draft YAML files
- Required fields present per object type
- Valid enum values (co_type, stage, cost_band, risk_band, lifecycle_state)
- Citation coverage (% of objects with at least one citation)
- Edge validity (all source/target slugs exist in drafts)
- Duplicate detection (slug collisions with existing database objects)
- Warns on missing `risk_band` when failure_modes exist
- Warns on missing `safety_boundary` when risk_band is `high` or `expert_only`
- Optionally writes `review_queue.json` (matching the conversion guide's review queue schema) for integration with a future review UI

## 10. Dependencies

Added as an `[ingest]` optional group in `pyproject.toml`:

```toml
[project.optional-dependencies]
ingest = [
    "marker-pdf>=1.0,<2.0",
    "openai>=1.0",
    "polars>=1.0",
    "orjson>=3.9",
    "rich>=13.0",
    "aiofiles>=24.0",
    "tiktoken>=0.7",
    "rapidfuzz>=3.0",
]
```

| Package | Purpose | Size |
|---------|---------|------|
| `marker-pdf` | ML-based PDF → markdown with page boundaries | ~500MB (with models) |
| `openai` | OpenAI-compatible chat completions client | Light |
| `polars` | Fast CSV/DataFrame operations for matrix and edges | ~15MB |
| `orjson` | Fast JSON/JSONL serialization | ~1MB |
| `rich` | Progress bars, colored tables, formatted reports | ~5MB |
| `aiofiles` | Async file I/O for segment reading in LLM passes | ~50KB |
| `tiktoken` | Token counting for cost estimation | ~5MB |
| `rapidfuzz` | Fuzzy string matching for canonicalization pre-grouping | ~3MB |

Core API server is unaffected — `[ingest]` is optional.

## 11. Documentation Requirements

Each CLI command must include:
- Clear `--help` output with description, arguments, flags, and examples
- Expected input/output files
- What the operator should review before proceeding to the next pass

The `ingestion/README.md` must be rewritten as a practical operator guide covering:
- Prerequisites and installation (`pip install -e ".[ingest]"`)
- End-to-end walkthrough with a pilot example
- Project directory reference
- Manifest configuration reference
- Per-pass documentation: what it does, what to review, common issues
- How to scope a pilot run (e.g., `--sections "Module 5"`)
- Cost estimation guidance
- Troubleshooting (LLM failures, marker issues, validation errors)

## 12. Testing Strategy

- **Unit tests** for each Pydantic model (validation, edge cases, malformed input).
- **Unit tests** for `project.py` (directory creation, manifest I/O, path resolution).
- **Unit tests** for `llm_client.py` (mock HTTP responses, retry behavior, validation failure handling).
- **Integration test** for `parse.py` with a small test PDF.
- **Integration test** for `load.py` extending `seed.py` — load a rich YAML with citations/edges, verify database records.
- **End-to-end test** with a fixture project directory containing pre-generated artifacts for each pass, verifying the full `validate` and `load` path.

LLM-dependent passes (extract, draft, cite, canonicalize, edges, bundles) are tested via:
- Mocked LLM responses that return known JSON.
- Verification that the pass correctly parses the response, writes the expected files, and handles validation errors.

## 13. Future Considerations

- **Community contributions via PR:** The project directory format is git-friendly. Contributors can run passes 0–5 locally, submit the project directory as a PR, and maintainers review + load. See memory note `project_community_ingestion.md`.
- **Batch parallelism:** Add `--concurrency N` flag to LLM passes for parallel section processing via `asyncio.gather` with semaphore.
- **Alternative PDF parsers:** The `parse` step can be extended to support `docling` or `pdfplumber` as alternatives to `marker` via a `--parser` flag.
- **Web UI for review:** A lightweight review interface for browsing drafts, approving/rejecting, and promoting lifecycle state.
- **Automated CI validation:** Run `ingest validate` in CI on PRs that touch `ingestion/projects/`.
