# Phase A: Stand Up Capability Commons

**Date:** 2026-03-13
**Status:** Approved

## Goal

Take the fully-implemented scaffold and stand it up as a working project at `~/Projects/CapabilityCommons/` with fresh git history, Docker-based Postgres+pgvector, and verified end-to-end operation.

## Architecture

- **Source:** Scaffold from `~/Projects/Capability Commons/scaffold/` promoted to project root
- **Stack:** FastAPI + async SQLAlchemy + Postgres 16 + pgvector + Alembic
- **Dev infra:** docker-compose for Postgres, local venv for app

## Project Structure

```
CapabilityCommons/
├── src/capability_commons/     # Application code
│   ├── api/                    # FastAPI routes
│   ├── db/                     # SQLAlchemy models, session
│   ├── domain/                 # Enums
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # Business logic
│   ├── search/                 # Search adapters (Postgres FTS)
│   ├── graph/                  # Graph adapters (relational BFS)
│   ├── retrieval/              # Retrieval planner + service
│   ├── publication/            # Public rendering + bundles
│   ├── storage/                # Object storage (stub)
│   ├── jobs/                   # Background jobs (stub)
│   ├── audit/                  # Audit logging (stub)
│   ├── config.py
│   └── main.py
├── tests/
├── alembic/
├── migrations/sql/
├── docs/
│   ├── spec/                   # Full implementation spec + checklist
│   ├── context/                # CONTEXT.md, INIT.md, SEED.md
│   └── plans/                  # This file
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── .env.example
├── .env                        # (gitignored)
├── .gitignore
└── README.md
```

## Steps

1. Copy scaffold to project root (done)
2. Move context docs (done)
3. Write `.gitignore`
4. Write `docker-compose.yml` (Postgres 16 + pgvector)
5. Verify/update `.env.example` and create `.env`
6. `git init` + initial commit
7. Create venv, install dependencies
8. Start Postgres via docker-compose
9. Run `alembic upgrade head`
10. Run tests
11. Start uvicorn, verify `/health`

## Out of Scope

- Authentication/authorization
- Embedding pipeline
- Knowledge graph seeding (Phase C — user will prepare expanded_seed data first)
- CI/CD
- Production hardening (pagination, rate limiting)
