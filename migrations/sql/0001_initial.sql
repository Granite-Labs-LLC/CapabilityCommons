CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE workspace_visibility AS ENUM ('public', 'private');

CREATE TYPE co_type AS ENUM (
  'concept_note',
  'skill_guide',
  'project_blueprint',
  'module',
  'assessment',
  'worksheet',
  'reference_sheet',
  'glossary',
  'teach_forward_packet',
  'learning_path',
  'field_report',
  'local_adaptation',
  'expert_review',
  'correction',
  'safety_notice',
  'translation',
  'community_map',
  'resource_directory'
);

CREATE TYPE lifecycle_state AS ENUM (
  'draft', 'in_review', 'reviewed', 'verified', 'published', 'deprecated', 'archived'
);

CREATE TYPE validity_status AS ENUM (
  'current', 'superseded', 'disputed', 'deprecated', 'retracted'
);

CREATE TYPE visibility_type AS ENUM (
  'public', 'contributor_only', 'editorial', 'restricted'
);

CREATE TYPE stage_type AS ENUM (
  'foundation', 'household', 'productive', 'community', 'advanced'
);

CREATE TYPE cost_band AS ENUM ('free', 'low', 'medium', 'high');

CREATE TYPE risk_band AS ENUM ('low', 'moderate', 'high', 'expert_only');

CREATE TYPE reading_level AS ENUM ('general', 'intermediate', 'technical');

CREATE TYPE facet_type AS ENUM (
  'domain',
  'audience',
  'housing_type',
  'settlement_type',
  'budget_profile',
  'climate_zone',
  'utility_profile',
  'locale',
  'language',
  'delivery_mode'
);

CREATE TYPE entity_type AS ENUM (
  'topic',
  'tool',
  'material',
  'hazard',
  'standard',
  'regulation',
  'organization',
  'person',
  'place',
  'climate_zone',
  'housing_type',
  'learner_profile',
  'community_asset'
);

CREATE TYPE entity_status AS ENUM ('active', 'deprecated', 'merged');

CREATE TYPE node_kind AS ENUM ('object_version', 'entity');

CREATE TYPE edge_type AS ENUM (
  'contains',
  'prerequisite_for',
  'builds_on',
  'assessed_by',
  'next_step_for',
  'alternative_to',
  'supported_by',
  'derived_from',
  'quotes',
  'summarizes',
  'validated_by',
  'contradicted_by',
  'supersedes',
  'deprecated_by',
  'corrected_by',
  'translated_from',
  'forked_from',
  'adapted_for',
  'applies_in',
  'requires_tool',
  'requires_material',
  'has_failure_mode',
  'mitigated_by',
  'unsafe_without',
  'bounded_by'
);

CREATE TYPE provenance_method AS ENUM (
  'human_authored',
  'deterministic_rule',
  'llm_extracted',
  'imported',
  'human_verified'
);

CREATE TYPE relation_status AS ENUM ('current', 'superseded', 'disputed', 'deprecated');

CREATE TYPE evidence_source_kind AS ENUM (
  'url',
  'file',
  'book',
  'standard',
  'field_observation',
  'transcript',
  'photo',
  'measurement',
  'external_doc'
);

CREATE TYPE trust_tier AS ENUM ('primary', 'secondary', 'field_note', 'anecdotal');

CREATE TYPE review_type AS ENUM (
  'editorial',
  'expert',
  'pedagogy',
  'safety',
  'translation',
  'fact_check'
);

CREATE TYPE review_outcome AS ENUM (
  'approved',
  'changes_requested',
  'rejected',
  'verified',
  'deprecated',
  'disputed'
);

CREATE TYPE contradiction_dimension AS ENUM (
  'factual',
  'safety',
  'currency',
  'regional',
  'terminology',
  'scope'
);

CREATE TYPE severity_level AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TYPE contradiction_status AS ENUM (
  'open',
  'triaged',
  'resolved',
  'accepted_contextual',
  'rejected'
);

CREATE TYPE retrieval_intent AS ENUM (
  'how_to',
  'learn_path',
  'why',
  'compare_options',
  'localize',
  'debug_failure',
  'teach_forward',
  'what_changed',
  'safety_check'
);

CREATE TYPE retrieval_run_status AS ENUM (
  'running',
  'completed',
  'failed',
  'budget_exhausted'
);

CREATE TYPE retrieval_step_type AS ENUM (
  'resolve_seeds',
  'search',
  'graph_expand',
  'rerank',
  'sufficiency',
  'assemble'
);

CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  visibility workspace_visibility NOT NULL DEFAULT 'public',
  default_language TEXT NOT NULL DEFAULT 'en',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE context_objects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  type co_type NOT NULL,
  canonical_title TEXT NOT NULL,
  current_version_id UUID NULL,
  lifecycle_state lifecycle_state NOT NULL DEFAULT 'draft',
  visibility visibility_type NOT NULL DEFAULT 'public',
  default_language TEXT NOT NULL DEFAULT 'en',
  created_by UUID NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ NULL,
  archived_at TIMESTAMPTZ NULL,
  UNIQUE (workspace_id, slug)
);

CREATE TABLE context_object_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  context_object_id UUID NOT NULL REFERENCES context_objects(id) ON DELETE CASCADE,
  version_no INTEGER NOT NULL,
  title TEXT NOT NULL,
  summary_short TEXT NULL,
  summary_medium TEXT NULL,
  summary_long TEXT NULL,
  plain_language TEXT NOT NULL,
  markdown_body TEXT NOT NULL,
  structured_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  validity_status validity_status NOT NULL DEFAULT 'current',
  valid_from TIMESTAMPTZ NULL,
  valid_to TIMESTAMPTZ NULL,
  stage stage_type NULL,
  difficulty SMALLINT NULL CHECK (difficulty BETWEEN 1 AND 5),
  estimated_minutes INTEGER NULL CHECK (estimated_minutes > 0),
  cost_band cost_band NOT NULL DEFAULT 'free',
  risk_band risk_band NOT NULL DEFAULT 'low',
  reading_level reading_level NOT NULL DEFAULT 'general',
  beginner_safe BOOLEAN NOT NULL DEFAULT TRUE,
  teach_forward_ready BOOLEAN NOT NULL DEFAULT FALSE,
  requires_professional BOOLEAN NOT NULL DEFAULT FALSE,
  source_confidence NUMERIC(3,2) NULL CHECK (source_confidence >= 0 AND source_confidence <= 1),
  evidence_confidence NUMERIC(3,2) NULL CHECK (evidence_confidence >= 0 AND evidence_confidence <= 1),
  locale_scope TEXT NOT NULL DEFAULT 'global',
  language_code TEXT NOT NULL DEFAULT 'en',
  supersedes_version_id UUID NULL REFERENCES context_object_versions(id),
  checksum TEXT NULL,
  created_by UUID NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (context_object_id, version_no),
  search_tsv TSVECTOR GENERATED ALWAYS AS (
    to_tsvector(
      'english',
      coalesce(title, '') || ' ' ||
      coalesce(summary_short, '') || ' ' ||
      coalesce(summary_medium, '') || ' ' ||
      coalesce(plain_language, '') || ' ' ||
      coalesce(markdown_body, '')
    )
  ) STORED
);

ALTER TABLE context_objects
  ADD CONSTRAINT fk_context_objects_current_version
  FOREIGN KEY (current_version_id)
  REFERENCES context_object_versions(id);

CREATE TABLE context_object_facets (
  context_object_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  facet_type facet_type NOT NULL,
  facet_value TEXT NOT NULL,
  PRIMARY KEY (context_object_version_id, facet_type, facet_value)
);

CREATE TABLE entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  entity_type entity_type NOT NULL,
  canonical_name TEXT NOT NULL,
  status entity_status NOT NULL DEFAULT 'active',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, entity_type, canonical_name)
);

CREATE TABLE entity_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  UNIQUE (entity_id, alias)
);

CREATE TABLE context_object_entities (
  context_object_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  mention_count INTEGER NOT NULL DEFAULT 1,
  role_label TEXT NULL,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (context_object_version_id, entity_id)
);

CREATE TABLE edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  src_node_kind node_kind NOT NULL,
  src_id UUID NOT NULL,
  edge_type edge_type NOT NULL,
  dst_node_kind node_kind NOT NULL,
  dst_id UUID NOT NULL,
  ordinal INTEGER NULL,
  confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
  provenance_method provenance_method NOT NULL DEFAULT 'human_authored',
  status relation_status NOT NULL DEFAULT 'current',
  valid_from TIMESTAMPTZ NULL,
  valid_to TIMESTAMPTZ NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by UUID NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE evidence_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  source_kind evidence_source_kind NOT NULL,
  title TEXT NOT NULL,
  uri TEXT NULL,
  citation_text TEXT NULL,
  trust_tier trust_tier NOT NULL DEFAULT 'secondary',
  license TEXT NULL,
  language_code TEXT NOT NULL DEFAULT 'en',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by UUID NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE evidence_spans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES evidence_sources(id) ON DELETE CASCADE,
  context_object_version_id UUID NULL REFERENCES context_object_versions(id) ON DELETE SET NULL,
  segment_id UUID NULL,
  start_char INTEGER NOT NULL CHECK (start_char >= 0),
  end_char INTEGER NOT NULL CHECK (end_char >= start_char),
  excerpt TEXT NOT NULL,
  checksum TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edge_evidence_spans (
  edge_id UUID NOT NULL REFERENCES edges(id) ON DELETE CASCADE,
  evidence_span_id UUID NOT NULL REFERENCES evidence_spans(id) ON DELETE CASCADE,
  PRIMARY KEY (edge_id, evidence_span_id)
);

CREATE TABLE review_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  context_object_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  review_type review_type NOT NULL,
  outcome review_outcome NOT NULL,
  reviewer_id UUID NULL,
  commentary TEXT NULL,
  checklist JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contradiction_cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  left_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  right_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  dimension contradiction_dimension NOT NULL,
  severity severity_level NOT NULL DEFAULT 'medium',
  status contradiction_status NOT NULL DEFAULT 'open',
  opened_by UUID NULL,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_by UUID NULL,
  resolved_at TIMESTAMPTZ NULL,
  resolution_note TEXT NULL,
  resolution_version_id UUID NULL REFERENCES context_object_versions(id) ON DELETE SET NULL
);

CREATE TABLE content_segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  context_object_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  text_content TEXT NOT NULL,
  token_count INTEGER NULL CHECK (token_count IS NULL OR token_count >= 0),
  embedding VECTOR(1536) NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (context_object_version_id, ordinal)
);

ALTER TABLE evidence_spans
  ADD CONSTRAINT fk_evidence_spans_segment
  FOREIGN KEY (segment_id)
  REFERENCES content_segments(id)
  ON DELETE SET NULL;

CREATE TABLE retrieval_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  requester_id UUID NULL,
  intent retrieval_intent NOT NULL,
  query_text TEXT NOT NULL,
  task_spec JSONB NOT NULL,
  compiled_plan JSONB NOT NULL DEFAULT '{}'::jsonb,
  status retrieval_run_status NOT NULL DEFAULT 'running',
  sufficiency_score NUMERIC(4,3) NOT NULL DEFAULT 0,
  budget_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ NULL
);

CREATE TABLE retrieval_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  retrieval_run_id UUID NOT NULL REFERENCES retrieval_runs(id) ON DELETE CASCADE,
  iteration_no INTEGER NOT NULL,
  step_type retrieval_step_type NOT NULL,
  query_text TEXT NULL,
  inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
  outputs JSONB NOT NULL DEFAULT '{}'::jsonb,
  latency_ms INTEGER NULL CHECK (latency_ms IS NULL OR latency_ms >= 0),
  budget_spent JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE object_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  context_object_version_id UUID NOT NULL REFERENCES context_object_versions(id) ON DELETE CASCADE,
  object_store_key TEXT NOT NULL,
  media_type TEXT NOT NULL,
  byte_size BIGINT NULL CHECK (byte_size IS NULL OR byte_size >= 0),
  checksum TEXT NULL,
  label TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE outbox_events (
  id BIGSERIAL PRIMARY KEY,
  aggregate_type TEXT NOT NULL,
  aggregate_id UUID NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_cov_context_object_id ON context_object_versions(context_object_id, version_no DESC);
CREATE INDEX idx_cov_validity ON context_object_versions(validity_status, created_at DESC);
CREATE INDEX idx_cov_search_tsv ON context_object_versions USING GIN(search_tsv);

CREATE INDEX idx_cof_facet_lookup ON context_object_facets(facet_type, facet_value, context_object_version_id);

CREATE INDEX idx_entities_lookup ON entities(workspace_id, entity_type, canonical_name);
CREATE INDEX idx_entity_alias_lookup ON entity_aliases(alias);

CREATE INDEX idx_edges_src ON edges(workspace_id, src_node_kind, src_id, edge_type);
CREATE INDEX idx_edges_dst ON edges(workspace_id, dst_node_kind, dst_id, edge_type);
CREATE INDEX idx_edges_status ON edges(status, created_at DESC);

CREATE INDEX idx_review_records_version ON review_records(context_object_version_id, created_at DESC);

CREATE INDEX idx_contradiction_cases_versions ON contradiction_cases(left_version_id, right_version_id);

CREATE INDEX idx_content_segments_version ON content_segments(context_object_version_id, ordinal);
CREATE INDEX idx_content_segments_embedding
  ON content_segments
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

CREATE INDEX idx_retrieval_runs_workspace_created_at ON retrieval_runs(workspace_id, created_at DESC);
CREATE INDEX idx_retrieval_steps_run_iteration ON retrieval_steps(retrieval_run_id, iteration_no, created_at);
CREATE INDEX idx_outbox_unprocessed ON outbox_events(processed_at) WHERE processed_at IS NULL;