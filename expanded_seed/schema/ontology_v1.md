# Capability Commons Seed Package v1

This package is a platform-neutral starter graph for the 25-node Capability Commons core.
It is designed to be imported into graph, relational, document, or hybrid knowledge systems.

## Contents

- `canonical/nodes/*.yaml`
  - One canonical seed file per node.
  - Full structured record, including nested `requires` logic and type-specific payload fields.
- `imports/nodes.jsonl`
  - Row-oriented full records for systems that ingest JSON Lines.
- `imports/nodes.csv`
  - Core scalar node fields only.
- `imports/node_payloads.csv`
  - Type-specific payload objects as JSON strings.
- `imports/node_requires.csv`
  - Normalized requirement groups preserving `all_of`, `any_of`, and `n_of` logic.
- `imports/edges.csv`
  - Direct node-to-node relations.
  - Includes pairwise `REQUIRES` edges plus recommended `NEXT` navigation edges.
- `imports/node_contexts.csv`
  - One row per node-context relationship.
- `imports/node_tags.csv`
  - One row per node-tag relationship.
- `imports/node_outputs.csv`
  - One row per node-output artifact relationship.
- `imports/nodes_wide.csv`
  - Convenience export with list-like fields stored as JSON strings.
- `imports/controlled_vocab.csv`
  - Controlled vocabularies used in the package.
- `imports/seed_manifest.csv`
  - Seed file path + SHA256 manifest.
- `workbook/capability_commons_import_sheets_v1.xlsx`
  - Spreadsheet version of the normalized import sheets.

## Design assumptions

- The 25 nodes are the starter capability graph only.
- Domains are treated as controlled vocabulary rather than first-class nodes in this package.
- `lifecycle_state` is set to `draft` for all nodes.
- `evidence_level` is set to `compiled` for all nodes.
- `source_refs` are intentionally left blank for local or future curation.
- The canonical date for this package is `2026-03-13`.

## Recommended import order

1. Load `imports/controlled_vocab.csv`.
2. Load `imports/nodes.csv`.
3. Load `imports/node_payloads.csv`.
4. Load child tables:
   - `imports/node_contexts.csv`
   - `imports/node_tags.csv`
   - `imports/node_outputs.csv`
5. Load `imports/node_requires.csv`.
6. Load `imports/edges.csv`.
7. Optionally load or diff against `imports/nodes.jsonl` and `canonical/nodes/*.yaml`.

## Type system

### `concept`
Explains a principle, model, or mental framework.

Payload keys:
- `definition`
- `key_questions`
- `misconceptions`
- `formulas_or_rules`
- `units`

### `skill`
Observable action a learner can perform.

Payload keys:
- `performance_statement`
- `inputs`
- `tools`
- `materials`
- `steps_summary`
- `success_criteria`
- `failure_modes`
- `safety_boundary`

### `project`
Applied task that creates a useful artifact or packet.

Payload keys:
- `goal`
- `deliverables`
- `acceptance_criteria`
- `time_box_hours`
- `budget_band`
- `team_size`

## Requirement logic

The canonical `requires` field is a list of grouped requirement objects.

Example:
```yaml
requires:
  - mode: all_of
    ids: [foundation.verify-and-cite]
    n: null
  - mode: n_of
    ids:
      - water.household-water-plan
      - food.pantry-design
      - food.beginner-garden-system
    n: 2
```

Normalized table representation:
- `source_id`
- `group_id`
- `mode`
- `group_n`
- `required_node_id`
- `requirement_order`

## Edge types

- `REQUIRES`
  - Direct pairwise dependency edges derived from `node_requires.csv`.
  - The `condition_group_id` column points back to the requirement group when group semantics matter.
- `NEXT`
  - Suggested navigation or progression edges.
  - These do not imply strict dependency.

## Validation rules

- Every node has a `plain_language` field.
- Every skill has at least one success criterion and one failure mode.
- Every project produces at least one durable output artifact.
- Every node has at least one output artifact.
- Every multi-value field appears both in canonical form and in normalized import tables.

## Counts

- Node records: 25
- Requirement rows: 50
- Edge rows: 77
- Output rows: 57
- Context rows: 152
- Tag rows: 125
