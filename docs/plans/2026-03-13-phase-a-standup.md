# Phase A: Stand Up Capability Commons — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Get the Capability Commons scaffold running as a real project with Postgres+pgvector, passing tests, and a responding API.

**Architecture:** FastAPI modular monolith backed by Postgres 16 + pgvector. Docker-compose for the database, local venv for the app. Alembic for schema migrations.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Alembic, Postgres 16, pgvector, pytest, Docker

---

### Task 1: Create .gitignore

**Files:**
- Create: `.gitignore`

**Step 1: Write .gitignore**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
.env
.DS_Store
*.db
*.sqlite3
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
```

**Step 2: Verify**

Run: `cat .gitignore | head -5`
Expected: first 5 lines visible

---

### Task 2: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

**Step 1: Write docker-compose.yml**

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: capability_commons
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

**Step 2: Verify file is valid YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`
Expected: no error (or install pyyaml if needed — not critical, visual check is fine)

---

### Task 3: Fix Alembic env.py for sync driver

**Files:**
- Modify: `alembic/env.py`
- Modify: `pyproject.toml` (add psycopg2-binary dependency)

**Context:** The current `alembic/env.py` uses `engine_from_config` (sync) but the DATABASE_URL uses `postgresql+asyncpg://` which requires an async driver. Alembic's standard `run_migrations_online` needs a sync connection.

**Step 1: Fix alembic/env.py to swap async URL to sync**

Replace the `settings` and `config.set_main_option` block with:

```python
settings = get_settings()
sync_url = settings.database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)
```

This converts `postgresql+asyncpg://...` to `postgresql://...` which uses the default sync psycopg2 driver.

**Step 2: Add psycopg2-binary to pyproject.toml**

Add `"psycopg2-binary>=2.9,<3.0"` to the `dependencies` list.

**Step 3: Verify the fix**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python3 -c "url='postgresql+asyncpg://x'; print(url.replace('+asyncpg', ''))"`
Expected: `postgresql://x`

---

### Task 4: Create .env from example

**Files:**
- Create: `.env` (copied from `.env.example`)

**Step 1: Copy .env.example to .env**

Run: `cp .env.example .env`

**Step 2: Verify**

Run: `cat .env | head -3`
Expected: `APP_ENV=dev`, `APP_NAME=...`, `API_V1_PREFIX=...`

---

### Task 5: Git init and initial commit

**Step 1: Initialize git**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && git init`
Expected: `Initialized empty Git repository`

**Step 2: Stage all files**

Run: `git add -A && git status`
Expected: all scaffold files staged, `.env` excluded by .gitignore

**Step 3: Initial commit**

```bash
git commit -m "feat: initial scaffold — Capability Commons Agentic Data Lite

Complete FastAPI scaffold with SQLAlchemy models, Pydantic schemas,
service layer, search/graph adapters, retrieval planner, and Alembic
migration for the Capability Commons knowledge substrate.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Create venv and install dependencies

**Step 1: Create virtual environment**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && python3 -m venv .venv`
Expected: `.venv/` directory created

**Step 2: Install project with dev dependencies**

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: all dependencies install successfully including fastapi, sqlalchemy, asyncpg, pgvector, psycopg2-binary, pytest, httpx

**Step 3: Verify import works**

Run: `source .venv/bin/activate && python3 -c "from capability_commons.main import app; print(app.title)"`
Expected: `Capability Commons API`

---

### Task 7: Start Postgres via docker-compose

**Step 1: Start the database**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && docker compose up -d`
Expected: `db` container starts, port 5432 exposed

**Step 2: Verify Postgres is ready**

Run: `docker compose exec db pg_isready -U postgres`
Expected: `/var/run/postgresql:5432 - accepting connections`

**Step 3: Verify pgvector extension is available**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname='vector';"`
Expected: `vector` in output

---

### Task 8: Run Alembic migration

**Step 1: Run upgrade head**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && source .venv/bin/activate && alembic upgrade head`
Expected: `Running upgrade  -> 20260313_0001, Initial Capability Commons Agentic Data Lite schema.`

**Step 2: Verify tables exist**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "\dt"`
Expected: tables including `context_objects`, `context_object_versions`, `edges`, `entities`, `evidence_sources`, `evidence_spans`, `review_records`, `contradiction_cases`, `content_segments`, `retrieval_runs`, `workspaces`, `outbox_events`, etc.

**Step 3: Verify enums exist**

Run: `docker compose exec db psql -U postgres -d capability_commons -c "SELECT typname FROM pg_type WHERE typtype='e' ORDER BY typname;"`
Expected: `co_type`, `lifecycle_state`, `validity_status`, `edge_type`, `stage_type`, etc.

---

### Task 9: Run tests

**Step 1: Run existing tests**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && source .venv/bin/activate && pytest tests/ -v`
Expected: `test_health` passes. Other tests may need DB — note results.

**Step 2: If any tests fail, diagnose and fix**

Common issues:
- `test_planner.py` or `test_structured_data.py` may need DB connection or may be unit tests
- Fix import errors if any

**Step 3: Commit any test fixes**

```bash
git add -A && git commit -m "fix: resolve test issues after project standup

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Verify API starts and responds

**Step 1: Start uvicorn**

Run: `cd /Users/nuggylover1210/Projects/CapabilityCommons && source .venv/bin/activate && uvicorn capability_commons.main:app --host 0.0.0.0 --port 8000 &`
Expected: `Uvicorn running on http://0.0.0.0:8000`

**Step 2: Hit health endpoint**

Run: `curl -s http://localhost:8000/health | python3 -m json.tool`
Expected: `{"status": "ok", "service": "capability_commons"}`

**Step 3: Hit detailed health**

Run: `curl -s http://localhost:8000/health/detailed | python3 -m json.tool`
Expected: JSON with `status`, `database`, `search`, `graph` keys

**Step 4: Check OpenAPI docs load**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs`
Expected: `200`

**Step 5: Stop uvicorn**

Run: `kill %1` (or `pkill -f uvicorn`)

**Step 6: Final commit**

```bash
git add -A && git commit -m "chore: phase A complete — project running with Postgres, migrations, and API

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Completion Checklist

- [ ] `.gitignore` created
- [ ] `docker-compose.yml` created with pgvector/pg16
- [ ] Alembic env.py fixed for sync driver
- [ ] psycopg2-binary added to dependencies
- [ ] `.env` created from example
- [ ] Git initialized with initial commit
- [ ] Venv created, deps installed
- [ ] Postgres running via docker-compose
- [ ] `alembic upgrade head` succeeds
- [ ] Tests pass
- [ ] `uvicorn` starts, `/health` returns 200
- [ ] OpenAPI docs accessible at `/docs`
