# Phase C: Seed the Knowledge Graph

**Date:** 2026-03-13
**Status:** Approved

## Goal

Build a reusable, idempotent CLI command that loads the 25-node starter graph from `expanded_seed/` into the running Postgres database.

## CLI Interface

```bash
python -m capability_commons.cli seed --data-dir expanded_seed/
```

- Creates a default workspace (`capability-commons`, public) if it doesn't exist
- Idempotent: uses `(workspace_id, slug)` uniqueness to skip existing objects
- Prints progress summary

## Data Sources

- **Nodes:** `expanded_seed/canonical/nodes/*.yaml` (25 files, canonical source)
- **NEXT edges:** `expanded_seed/imports/edges.csv` (rows where edge_type=NEXT)
- **REQUIRES edges:** embedded in each YAML file's `requires` field

## Data Flow Per Node

```
YAML file
  → context_objects (slug=node id, co_type mapped)
  → context_object_versions (v1, structured_data from payload)
  → context_object_facets (domain + context facets)
  → edges (prerequisite_for from requires field)
```

## Type Mapping

| Seed `type` | DB `co_type` |
|---|---|
| `skill` | `skill_guide` |
| `concept` | `concept_note` |
| `project` | `project_blueprint` |

## Edge Mapping

| Seed edge | DB `edge_type` |
|---|---|
| `REQUIRES` | `prerequisite_for` |
| `NEXT` | `next_step_for` |

## Facet Mapping

- `primary_domain` → `facet_type='domain'`
- `general`, `renter`, `homeowner` → `facet_type='audience'`
- `urban`, `rural`, `off_grid` → `facet_type='settlement_type'`
- `low_budget` → `facet_type='budget_profile'`

## Tags and Outputs

Stored in `structured_data` JSONB alongside the type-specific payload fields.

## Out of Scope

- Embedding generation
- Content segment chunking
- Lifecycle transitions (everything stays `draft`)
- Outbox event emission
