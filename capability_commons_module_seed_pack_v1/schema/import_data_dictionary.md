# Import Data Dictionary

This document describes the import files in the module seed pack.

## Shared core tables

### `imports/nodes.csv`
Scalar node fields only.
Use for systems that prefer a flat node table.

### `imports/node_payloads.csv`
Contains the nested payload for each node as a JSON string.

### `imports/node_requires.csv`
Normalized requirement groups with these columns:
- `source_id`
- `group_id`
- `mode`
- `group_n`
- `required_node_id`
- `requirement_order`
- `note`

### `imports/edges.csv`
Graph-ready edge table with these columns:
- `edge_id`
- `source_id`
- `edge_type`
- `target_id`
- `condition_group_id`
- `sequence`
- `note`

### `imports/node_outputs.csv`
One row per output artifact label.

### `imports/node_contexts.csv`
One row per context label.

### `imports/node_tags.csv`
One row per tag.

### `imports/nodes_wide.csv`
Convenience wide export with array-like fields stored as JSON strings.

## Curriculum-specific tables

### `imports/module_node_refs.csv`
Main curriculum-to-graph crosswalk.
Columns:
- `module_id`
- `node_id`
- `node_order`
- `coverage_mode`
- `coverage_weight`
- `note`

### `imports/module_learning_objectives.csv`
One row per learning objective.

### `imports/module_schedule.csv`
Delivery profile in minutes.
Columns:
- `module_id`
- `week`
- `seminar_minutes`
- `lab_minutes`
- `field_task_minutes`
- `teach_forward_minutes`
- `total_minutes`

### `imports/module_deliverables.csv`
Module deliverables keyed back to the source capability node where available.
Columns:
- `module_id`
- `deliverable_order`
- `deliverable_key`
- `deliverable_label`
- `source_node_id`
- `required_for_pass`

### `imports/assessment_rubric_rows.csv`
One row per rubric criterion.
Columns:
- `assessment_id`
- `criterion_order`
- `criterion_type`
- `criterion_text`
- `critical`

### `imports/assessment_evidence.csv`
One row per required assessment evidence item.
Columns:
- `assessment_id`
- `evidence_order`
- `evidence_key`
- `evidence_label`
- `required_for_pass`

### `imports/node_curriculum_alignment.csv`
Convenience table for reporting or navigation.
Columns:
- `node_id`
- `node_title`
- `first_module_id`
- `first_week`
- `last_module_id`
- `last_week`
- `module_sequence_json`
- `assessment_sequence_json`
- `coverage_modes_json`
- `node_outputs_json`
