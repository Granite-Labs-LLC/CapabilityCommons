# Capability Commons Module Seed Pack v1

This package adds curriculum-layer nodes to the Capability Commons starter graph.

It is designed to **merge cleanly** with the existing `capability_commons_seed_package_v1` by simple union of shared import tables:
- `imports/nodes.csv`
- `imports/node_payloads.csv`
- `imports/node_requires.csv`
- `imports/edges.csv`
- `imports/node_outputs.csv`
- `imports/node_contexts.csv`
- `imports/node_tags.csv`
- `imports/nodes.jsonl`

The record and table model remains platform-neutral so it can be adapted to graph, relational, document, or hybrid systems.

## Package contents

- `canonical/nodes/*.yaml`
  - One canonical seed file per module or assessment.
- `imports/nodes.jsonl`
  - Full curriculum records as JSON Lines.
- `imports/nodes.csv`
  - Scalar node fields only.
- `imports/node_payloads.csv`
  - Type-specific payload objects as JSON strings.
- `imports/node_requires.csv`
  - Normalized requirement groups preserving `all_of` and `n_of`.
- `imports/edges.csv`
  - Curriculum edges, including `REQUIRES`, `COVERS`, `ASSESSED_BY`, `EVALUATES`, and `PRECEDES`.
- `imports/node_outputs.csv`
  - One row per node-output relationship.
- `imports/node_contexts.csv`
  - One row per node-context relationship.
- `imports/node_tags.csv`
  - One row per node-tag relationship.
- `imports/nodes_wide.csv`
  - Convenience export with list-like fields stored as JSON strings.
- `imports/module_node_refs.csv`
  - Module-to-capability crosswalk with coverage weight.
- `imports/module_learning_objectives.csv`
  - One row per module learning objective.
- `imports/module_schedule.csv`
  - Delivery time profile by module.
- `imports/module_deliverables.csv`
  - Module deliverables mapped back to source capability node IDs.
- `imports/assessment_rubric_rows.csv`
  - Rubric criteria broken into evaluable rows.
- `imports/assessment_evidence.csv`
  - Required evidence rows for each assessment.
- `imports/node_curriculum_alignment.csv`
  - First/last curriculum touchpoints for each covered capability node.
- `imports/controlled_vocab.csv`
  - Controlled vocabularies used by this package.
- `imports/seed_manifest.csv`
  - Seed file path + SHA256 manifest.
- `workbook/capability_commons_module_import_sheets_v1.xlsx`
  - Spreadsheet version of the normalized import sheets.

## Design assumptions

- This package introduces **24 curriculum nodes**:
  - 12 `module` nodes
  - 12 `assessment` nodes
- Capability node IDs referenced in `module.payload.node_refs` come from the existing 25-node starter graph.
- `source_refs` are intentionally blank to allow local or later curation.
- All curriculum nodes begin at:
  - `lifecycle_state = draft`
  - `evidence_level = compiled`
- The canonical package date for this module pack is `2026-03-16`.

## Key alignment table

`imports/module_node_refs.csv` is the main handoff table between curriculum delivery and graph ingestion.

Columns:
- `module_id`
- `node_id`
- `node_order`
- `coverage_mode`
- `coverage_weight`
- `note`

`coverage_mode` is the pedagogical relationship between the module and the capability node.
`coverage_weight` indicates whether a node is the main target of the week or a supporting concept/skill.

## Edge semantics

- `REQUIRES`
  - Direct prerequisite relationship between curriculum nodes.
  - `condition_group_id` points back to grouped requirement logic in `node_requires.csv`.
- `COVERS`
  - Module covers a capability node from the 25-node graph.
- `ASSESSED_BY`
  - Module points to its paired assessment.
- `EVALUATES`
  - Assessment evaluates one or more capability nodes covered by the module.
- `PRECEDES`
  - Delivery sequence edge between modules.

## Merge guidance

To merge this package with the base capability node package:

1. Load or concatenate the shared import tables.
2. Preserve `id` uniqueness across both packages.
3. Retain the existing capability node IDs as authoritative for skill/concept/project objects.
4. Use `module.payload.node_refs` or `imports/module_node_refs.csv` to connect curriculum delivery to the existing graph.

Because this package only introduces new IDs of type `module` and `assessment`, no capability node IDs are duplicated.

## Counts

- Curriculum nodes: 24
- Modules: 12
- Assessments: 12
- Requirement rows: 25
- Edge rows: 98
- Module-to-node rows: 25
- Deliverable rows: 57
- Alignment rows: 25
