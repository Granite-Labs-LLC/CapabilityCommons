# Capability Commons Module Seed Pack v1

This package adds a curriculum layer keyed to the existing 25-node Capability Commons starter graph.

## Included formats

- Canonical seed files: `canonical/nodes/*.yaml`
- Full-record import: `imports/nodes.jsonl`
- Flat import sheets: `imports/*.csv`
- Spreadsheet workbook: `workbook/capability_commons_module_import_sheets_v1.xlsx`
- Schema and mapping docs: `schema/*`

## Package counts

- Curriculum nodes: 24
- Modules: 12
- Assessments: 12
- Requirement rows: 25
- Edge rows: 98
- Module-to-node rows: 25
- Deliverable rows: 57
- Alignment rows: 25

## Canonical record rule

If a field differs between formats, treat the YAML seed files and `imports/nodes.jsonl` as authoritative.
The flat CSV tables are normalized projections for ingestion convenience.

## Import options

### Option A: document / object ingestion
Use:
- `canonical/nodes/*.yaml` or
- `imports/nodes.jsonl`

### Option B: normalized relational / graph ingestion
Use:
- `imports/nodes.csv`
- `imports/node_payloads.csv`
- `imports/node_requires.csv`
- `imports/edges.csv`
- plus child tables for contexts, tags, and outputs
- plus curriculum-specific crosswalk tables

### Option C: merge with the base capability package
Union the shared core import tables with the existing capability node package, then add:
- `imports/module_node_refs.csv`
- `imports/module_learning_objectives.csv`
- `imports/module_schedule.csv`
- `imports/module_deliverables.csv`
- `imports/assessment_rubric_rows.csv`
- `imports/assessment_evidence.csv`
- `imports/node_curriculum_alignment.csv`

## Notes

- Capability node IDs referenced in modules come from `capability_commons_seed_package_v1`.
- This package introduces only new IDs of type `module` and `assessment`.
- `source_refs` are blank by design so your team can attach local or canonical citations later.
- All nodes begin at `lifecycle_state = draft` and `evidence_level = compiled`.
- `module_node_refs.csv` is the main curriculum-to-graph handoff table.

See `schema/ontology_v1.md` and `schema/import_data_dictionary.md` for the field model and loading guidance.
