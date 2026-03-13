# Capability Commons — Agentic Data Lite Scaffold

This is a Postgres-first FastAPI scaffold generated from the Capability Commons Agentic Data Lite specification.

It includes:

- async FastAPI application with v1 routes from the spec
- SQLAlchemy 2 async ORM models for the canonical schema
- Pydantic v2 request/response models and structured-data validators
- service-layer boundaries for registry, evidence, review, search, graph, retrieval, and publication
- Alembic bootstrapping plus the initial SQL schema from the design pack
- a relational graph adapter and a Postgres search adapter for v1
- retrieval-run persistence and a starter evidence-pack planner

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn capability_commons.main:app --reload
```

## Project layout

```text
src/capability_commons/
  api/           # FastAPI routes and dependencies
  db/            # Async engine, session, ORM models
  domain/        # Enums and shared domain constants
  schemas/       # Pydantic request/response models
  services/      # Registry, entities, evidence, review
  search/        # Chunking and Postgres search adapter
  graph/         # Relational graph adapter
  retrieval/     # Planner and evidence-pack assembly
  publication/   # Public rendering helpers
```

## What is implemented

- Canonical object/version creation and publication lifecycle
- Facet, entity, edge, citation, review, contradiction, and retrieval-run records
- Type-specific `structured_data` validation for the v1 object types listed in the spec
- Relational graph traversal for neighbors, ordered membership, and reverse prerequisite lookup
- Lexical Postgres full-text search for version retrieval
- A starter retrieval planner with intent-specific edge sets and sufficiency scoring

## What is intentionally still a scaffold

- Vector embeddings are optional and default to `NULL`
- Outbox consumers, static export generation, and object storage upload flows are left as extension points
- Entity merge and advanced contradiction auto-detection are stubs
- Neo4j and OpenSearch adapters are represented by interfaces only

## Notes for developers

- The initial migration executes the provided canonical SQL schema directly.
- The ORM models match the schema closely, but the raw SQL migration remains the migration source of truth for v1.
- Search and graph stay behind adapter interfaces so OpenSearch or Neo4j can be added later without changing the API surface.
