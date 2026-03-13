# Capability Commons Seed Package v1

This package contains a platform-neutral starter graph for the 25-node Capability Commons core.

## Included formats

- Canonical seed files: `canonical/nodes/*.yaml`
- Full-record import: `imports/nodes.jsonl`
- Flat import sheets: `imports/*.csv`
- Spreadsheet workbook: `workbook/capability_commons_import_sheets_v1.xlsx`
- Schema and mapping docs: `schema/*`

## Package counts

- Nodes: 25
- Requirement rows: 50
- Edge rows: 77
- Output rows: 57
- Context rows: 152
- Tag rows: 125

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

### Option C: single wide sheet
Use:
- `imports/nodes_wide.csv`

## Notes

- Domain membership is stored as a scalar field (`primary_domain`) plus a one-item list (`domains`).
- Domains are not emitted as first-class graph nodes in this package.
- `source_refs` are blank by design so your team can attach local or canonical citations later.
- All nodes begin at `lifecycle_state = draft` and `evidence_level = compiled`.

See `schema/ontology_v1.md` and `schema/import_data_dictionary.md` for the field model and loading guidance.
