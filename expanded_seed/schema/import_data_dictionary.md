# Import data dictionary

## `nodes.csv`
One row per node with scalar fields only.

Columns:
- `id`
- `type`
- `title`
- `summary`
- `plain_language`
- `primary_domain`
- `stage`
- `difficulty`
- `estimated_hours`
- `cost_band`
- `risk_band`
- `lifecycle_state`
- `evidence_level`
- `version`
- `updated_at`

## `node_payloads.csv`
Type-specific content stored as JSON.

Columns:
- `node_id`
- `type`
- `payload_json`

## `node_requires.csv`
Normalized prerequisite logic.

Columns:
- `source_id`
- `group_id`
- `mode`
- `group_n`
- `required_node_id`
- `requirement_order`
- `note`

## `edges.csv`
Direct node-to-node relations.

Columns:
- `edge_id`
- `source_id`
- `edge_type`
- `target_id`
- `condition_group_id`
- `sequence`
- `note`

## `node_outputs.csv`
Durable output artifacts produced by a node.

Columns:
- `node_id`
- `output_name`
- `output_order`

## `node_contexts.csv`
Context variants or intended use environments.

Columns:
- `node_id`
- `context`
- `context_order`

## `node_tags.csv`
Retrieval tags.

Columns:
- `node_id`
- `tag`
- `tag_order`

## `nodes_wide.csv`
Single-file convenience export.

List-like fields are serialized as JSON strings.

## `nodes.jsonl`
Full canonical records serialized one per line.

## `seed_manifest.csv`
Maps node IDs to canonical seed files and SHA256 hashes.
