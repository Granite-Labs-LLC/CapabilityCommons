# Capability Commons

A Postgres-first knowledge platform for practical, public capability literacy. Built on the Agentic Data Lite architecture — a trimmed version of the enterprise AgenticData stack focused on versioned knowledge objects, typed edges, evidence provenance, and retrieval planning.

The unit of value is the **reproducible capability**: every node in the system explains something people need to understand, trains something people need to do, or produces something people can keep, use, and teach forward.

## Vision

The goal is to take knowledge that is usually trapped inside trades, institutions, guilds, paywalls, jargon, or credential barriers and turn it into understandable concepts, reproducible skills, local practical action, and teach-forward transmission.

> AI should be used to convert hidden competence into shared public capacity.

Six rules govern the commons: **open by default**, **practical before ornamental**, **layered for beginners**, **locally adaptable**, **project-based**, and **teach-forward**. The system is built around three interlocking graphs — a concept graph (what things mean), a skill graph (what people can do), and a deployment graph (how it applies in your actual life).

See [`docs/VISION.md`](docs/VISION.md) for the full doctrine, knowledge object model, publishing rules, assessment model, governance principles, and success metrics.

## Architecture

- **Postgres 16 + pgvector** as the single source of truth
- **FastAPI** async API with v1 routes
- **SQLAlchemy 2** async ORM with 19 tables
- **Alembic** migrations
- **Docker Compose** for local development
- Adapter interfaces for optional Neo4j and OpenSearch when needed later

### Knowledge object types

Seed data uses three types, mapped to the internal type system:

| Seed type | Internal type | Purpose |
|-----------|--------------|---------|
| `skill` | `skill_guide` | Observable action a learner can perform |
| `concept` | `concept_note` | Principle, model, or mental framework |
| `project` | `project_blueprint` | Applied task that creates a useful artifact |
| `module` | `module` | Weekly curriculum unit covering multiple capabilities |
| `assessment` | `assessment` | Evaluation rubric for a module |

### Edge types

| Seed edge | Internal edge | Meaning |
|-----------|--------------|---------|
| `REQUIRES` | `prerequisite_for` | Source depends on target |
| `NEXT` | `next_step_for` | Suggested navigation/progression |
| `COVERS` | `contains` | Module covers a capability node |
| `ASSESSED_BY` | `assessed_by` | Module assessed by an assessment |
| `EVALUATES` | `validated_by` | Assessment evaluates a capability |
| `PRECEDES` | `next_step_for` | Module sequencing (maps to next_step_for) |

The schema supports 25 edge types total — see `src/capability_commons/domain/enums.py`.

## Current state

### Seeded knowledge graph

The full graph is loaded in two passes — 25 capability nodes and 24 curriculum nodes:

| Metric | Count |
|--------|-------|
| Context objects | 49 (25 capability + 12 modules + 12 assessments) |
| Versions | 49 |
| Facets | 167+ (domain, audience, settlement_type, budget_profile) |
| Edge types | 5 (prerequisite_for, next_step_for, contains, assessed_by, validated_by) |
| Total edges | 175 (77 from capability seed + 98 from curriculum seed) |

Domains covered: foundation (5 nodes), water (4), food (5), shelter (3), repair (2), power (4), community (2).
Curriculum: 12 weekly modules + 12 matching assessments spanning all domains.

### Working services

- FastAPI application with health check, CORS, and v1 routes
- Object/version CRUD with lifecycle management (draft/reviewed/verified/deprecated)
- Relational graph traversal (neighbors, prerequisites, membership)
- Postgres full-text search
- Retrieval planner with intent-specific edge sets
- Idempotent seed CLI

### Extension points (not yet active)

- Vector embeddings (pgvector columns exist, default to `NULL`)
- Evidence-pack assembly and contradiction workflows
- Outbox consumers, static export, object storage uploads
- Neo4j and OpenSearch adapters (interfaces defined)
- Entity merge and advanced contradiction auto-detection

## Quick start

```bash
# 1. Start Postgres
docker compose up -d

# 2. Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Configure
cp .env.example .env
# Default DATABASE_URL uses port 5433 (remapped from 5432)

# 4. Run migrations
alembic upgrade head

# 5. Seed the knowledge graph (two passes)
python -m capability_commons.cli.seed --data-dir expanded_seed/
python -m capability_commons.cli.seed --data-dir capability_commons_module_seed_pack_v1/

# 6. Start the API
uvicorn capability_commons.main:app --reload --port 8100
```

### Verify the seed

```bash
# Check object counts
docker compose exec db psql -U postgres -d capability_commons \
  -c "SELECT type, count(*) FROM context_objects GROUP BY type;"

# Check edge counts
docker compose exec db psql -U postgres -d capability_commons \
  -c "SELECT edge_type, count(*) FROM edges GROUP BY edge_type;"

# Re-run is idempotent
python -m capability_commons.cli.seed --data-dir expanded_seed/
# → "Seed complete: 0 objects created, 25 skipped, ..."
python -m capability_commons.cli.seed --data-dir capability_commons_module_seed_pack_v1/
# → "Seed complete: 0 objects created, 24 skipped, ..."
```

## Project layout

```text
src/capability_commons/
  api/           # FastAPI routes, dependencies, error handlers
  audit/         # Audit trail
  cli/           # CLI commands (seed loader)
  db/            # Async engine, session, ORM models (19 tables)
  domain/        # Enums and shared domain constants
  graph/         # Relational graph adapter
  jobs/          # Background job stubs
  publication/   # Public rendering helpers
  retrieval/     # Planner and evidence-pack assembly
  schemas/       # Pydantic request/response models
  search/        # Chunking and Postgres search adapter
  services/      # Registry, entities, evidence, review
  storage/       # Object storage adapter interface

expanded_seed/                           # 25-node capability seed data
  canonical/nodes/*.yaml                 # Authoritative source (one per node)
  imports/*.csv                          # Normalized relational tables
  imports/nodes.jsonl                    # Full-record JSON Lines
  schema/                                # JSON schemas and data dictionary

capability_commons_module_seed_pack_v1/  # 24-node curriculum seed data
  canonical/nodes/*.yaml                 # 12 modules + 12 assessments
  imports/edges.csv                      # 98 edges (COVERS, ASSESSED_BY, etc.)
  schema/                                # Ontology and data dictionary

docs/
  VISION.md                # Project purpose, doctrine, and design model
  context/                 # Original design rationale documents
  plans/                   # Implementation plans
  spec/                    # Agentic Data Lite specification

alembic/                   # Database migrations
docker-compose.yml         # Postgres 16 + pgvector
```

## Seed data

The `expanded_seed/` directory contains the canonical 25-node starter graph in multiple formats:

- **Canonical source**: `canonical/nodes/*.yaml` — one file per node with full structured payloads
- **Relational import**: `imports/nodes.csv`, `imports/edges.csv`, and child tables
- **Document import**: `imports/nodes.jsonl` — full records, one per line
- **Spreadsheet**: `workbook/capability_commons_import_sheets_v1.xlsx`

If formats disagree, YAML and JSONL are authoritative. See `expanded_seed/schema/ontology_v1.md` for the full field model.

## Configuration

Key environment variables (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/capability_commons` | Async database connection |
| `EMBEDDING_DIM` | `1536` | pgvector embedding dimension |
| `DEFAULT_TOP_K` | `20` | Search result limit |
| `DEFAULT_MAX_GRAPH_DEPTH` | `3` | Graph traversal depth |
| `DEFAULT_SUFFICIENCY_THRESHOLD` | `0.75` | Retrieval planner threshold |

## Development

```bash
# Run tests
pytest -v

# Run specific test file
pytest tests/test_seed.py -v
```

## Design principles

- **Postgres-first**: single source of truth, optional graph/search projections later
- **Versioned knowledge objects**: every edit creates a new version, old versions preserved
- **Typed edges with provenance**: edges carry confidence, method, and status
- **Context-aware facets**: domain, audience, settlement type, budget profile, climate zone
- **Idempotent operations**: seed and import commands are safe to re-run
- **Barrier-lowering by design**: plain language, low-cost paths, renter/homeowner variants
- **Teach-forward model**: every capability should be explainable to another person
