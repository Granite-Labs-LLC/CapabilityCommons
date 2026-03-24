# Ingestion Pipeline — Operator Guide

Convert source documents (PDFs, manuals) into fully populated Capability Commons knowledge objects with citations, edges, and learning bundles.

## Prerequisites

```bash
# From the project root
pip install -e '.[ingest]'

# Required: an OpenAI-compatible API key
export OPENAI_API_KEY="sk-..."
```

The `[ingest]` extra installs: marker-pdf, polars, rich, aiofiles, tiktoken, rapidfuzz.

## Quick Start

```bash
# 1. Initialize a project
python -m capability_commons.cli.ingest init my-project \
  --source path/to/document.pdf \
  --source-id src.myproject.refbook.2024 \
  --source-title "My Reference Book" \
  --source-kind BOOK

# 2. Run the pipeline pass by pass
python -m capability_commons.cli.ingest parse my-project
python -m capability_commons.cli.ingest extract my-project
python -m capability_commons.cli.ingest draft my-project
python -m capability_commons.cli.ingest cite my-project
python -m capability_commons.cli.ingest canonicalize my-project
python -m capability_commons.cli.ingest edges my-project
python -m capability_commons.cli.ingest bundles my-project

# 3. Validate before loading
python -m capability_commons.cli.ingest validate my-project

# 4. Load to database
python -m capability_commons.cli.ingest load my-project --publish
```

## Project Directory Structure

After initialization, your project lives at `ingestion/projects/<name>/`:

```
my-project/
├── manifest.yaml          # Project config, source list, pass status
├── sources/               # Source PDFs (copied on init)
│   └── document.pdf
├── segments/              # Pass 0 output
│   ├── segments.jsonl     # Page-preserving text segments
│   └── source_manifest.yaml
├── matrix/                # Pass 1 output
│   └── extraction_matrix.csv
├── drafts/                # Passes 2-6 output
│   ├── water.safe-storage.yaml
│   ├── water.treatment.yaml
│   ├── _merged/           # Deprecated drafts (from canonicalize)
│   ├── _split/            # Split originals (from canonicalize)
│   ├── canonicalization_log.json
│   └── evidence_map.json
├── edges/                 # Pass 5 output
│   └── edges.csv
└── output/                # Pass 7 output (seed-compatible)
    ├── canonical/nodes/
    └── imports/edges.csv
```

## Pipeline Passes

### Pass 0: Parse (`parse`)

Converts source PDFs to markdown using marker-pdf, then splits into heading-delimited segments.

**Output:** `segments/segments.jsonl` — one JSON object per segment with `source_id`, `segment_id`, `page_start`, `page_end`, `heading_path`, and `text`.

**What to review:** Check segment count and heading paths. If the PDF has unusual formatting, segments may need manual adjustment.

### Pass 1: Extract (`extract`)

Sends segments to the LLM in section groups. Each section produces extraction matrix rows identifying candidate knowledge objects.

**Output:** `matrix/extraction_matrix.csv` — one row per candidate with slug, type, domain, stage, summary, and confidence.

**Options:**
- `--sections "Water"` — filter to sections matching a string (case-insensitive)

**What to review:** Check candidate slugs, types, and confidence scores. Remove or adjust low-confidence rows before drafting.

### Pass 2: Draft (`draft`)

For each matrix row, sends the candidate info + source segments to the LLM to produce a full canonical YAML object.

**Output:** `drafts/<slug>.yaml` — one file per object with title, body, structured data, prerequisites, and suggested edges.

**Options:**
- `--skip-existing` — skip slugs that already have draft files
- `--slugs "water.*"` — filter to slugs matching a glob pattern

**What to review:** Read the markdown_body for accuracy. Check structured_data fields. Verify prerequisites make sense.

### Pass 3: Cite (`cite`)

Links claims in each draft's markdown_body back to supporting source spans.

**Output:** Citations are written into each draft YAML's `citations` field. An `evidence_map.json` is also written.

**Options:**
- `--slugs "water.*"` — filter to specific slugs

**What to review:** Check citation coverage (validate command reports this). Verify support_strength ratings.

### Pass 4: Canonicalize (`canonicalize`)

Uses rapidfuzz similarity matching to find potential duplicates, then asks the LLM to decide: keep, merge, or split.

**Output:** Merged/split drafts moved to `_merged/` and `_split/` subdirectories. A `canonicalization_log.json` records all decisions.

**What to review:** Check the log for merge decisions. Verify no important content was lost.

### Pass 5: Edges (`edges`)

Sends object summaries to the LLM to infer typed relationships (prerequisite_for, builds_on, contains, etc.). Merges with any `suggested_edges` already in drafts.

**Output:** `edges/edges.csv` — columns: source_id, target_id, edge_type, sequence, condition, confidence.

**What to review:** Check that prerequisite chains make sense. Look for missing obvious edges.

### Pass 6: Bundles (`bundles`)

Generates six-part learning bundles for skill_guide, project_blueprint, and module objects: hook, primer, guide, reference, worksheet, teach-forward kit.

**Output:** `bundle_overrides` field added to each eligible draft YAML.

**Options:**
- `--skip-existing` — skip objects that already have bundles
- `--slugs "water.*"` — filter to specific slugs

**What to review:** Read the hook and primer for clarity. Check worksheet exercises for practicality.

### Pass 7: Load (`load`)

Validates all drafts and edges, writes seed-compatible output, then loads to the database via `seed_graph()`.

**Options:**
- `--publish` — set lifecycle_state to PUBLISHED on all objects
- `--dry-run` — validate and write output only, skip database load
- `--db-url` — override database URL (default: from .env)

### Validate (`validate`)

Checks all drafts for: required fields, valid enum values (co_type, stage, cost_band, risk_band, lifecycle_state), edge integrity (source/target exist), and citation coverage.

### Status (`status`)

Shows a table of all passes with completion timestamps and file counts.

## LLM Configuration

The manifest's `llm` section sets defaults:

```yaml
llm:
  base_url: https://api.openai.com/v1
  model: gpt-4o
  temperature: 0.2
```

Override per-command with CLI flags:

```bash
python -m capability_commons.cli.ingest extract my-project \
  --model gpt-4o-mini \
  --temperature 0.1
```

All LLM passes show estimated input token counts and require confirmation before proceeding. Use `--yes` / `-y` to skip prompts for scripted runs.

## Scoping a Pilot Run

For a first run, limit scope to reduce cost and review burden:

```bash
# Extract only one section
python -m capability_commons.cli.ingest extract my-project --sections "Chapter 1"

# Draft only specific slugs
python -m capability_commons.cli.ingest draft my-project --slugs "water.*"

# Dry-run the load to see output without touching the database
python -m capability_commons.cli.ingest load my-project --dry-run
```

## Cost Estimation

Each LLM pass prints estimated input tokens before prompting for confirmation. Rough cost guidance (GPT-4o pricing):

| Pass | Typical tokens per object | Notes |
|------|--------------------------|-------|
| Extract | 2,000-5,000 input | Per section group |
| Draft | 3,000-8,000 input | Per object |
| Cite | 5,000-15,000 input | Per object (includes segment context) |
| Canonicalize | 2,000-5,000 input | Per duplicate group (often few) |
| Edges | 5,000-20,000 input | Single call with all summaries |
| Bundles | 3,000-8,000 input | Per bundleable object |

## Troubleshooting

**`marker-pdf` import error:** Install with `pip install -e '.[ingest]'`. Marker requires additional system dependencies on some platforms.

**LLM validation failures:** The client retries up to 3 times with error feedback. If a pass consistently fails, try a more capable model (`--model gpt-4o`) or lower temperature.

**Empty extraction matrix:** Check that segments were generated correctly (`status` command). The PDF may need a different parsing approach.

**Edge validation errors:** Usually means a slug in edges.csv doesn't match any draft file. Check for typos or objects removed during canonicalization.

## Methodology Reference

For the full methodology behind the multi-pass pipeline, see `corpus_conversion_guide.md` in this directory.
