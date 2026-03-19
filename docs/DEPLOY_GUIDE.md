# Loading the Full Graph and Deploying to the Website

This guide walks through seeding the full Capability Commons knowledge graph (25 capability nodes + 24 curriculum nodes + all edges) and connecting it to the CapabilityCommonsSite frontend.

## Prerequisites

- Python 3.11+ with the `capability-commons-agentic-lite` package installed
- Docker and Docker Compose
- Node.js 22.12+
- The three project directories:
  - `~/Projects/CapabilityCommons/` — Backend API
  - `~/Projects/CapabilityCommonsSite/` — Frontend website

## 1. Start the Backend

### Option A: Docker Compose (recommended)

```bash
cd ~/Projects/CapabilityCommons
docker compose up -d
```

This starts:
- **Postgres 16 + pgvector** on port `5433` (host) / `5432` (container)
- **FastAPI API** on port `8100`

Wait for healthy status:

```bash
docker compose ps
# Both services should show "healthy"
```

### Option B: Local development

```bash
cd ~/Projects/CapabilityCommons
cp .env.example .env

# Start Postgres with pgvector (must have pg16 + pgvector locally)
# Edit .env if your DB is on a different port

source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Run Migrations

If using Docker Compose, exec into the API container:

```bash
docker compose exec api alembic upgrade head
```

If running locally:

```bash
cd ~/Projects/CapabilityCommons
source .venv/bin/activate
alembic upgrade head
```

This creates all tables including the `idx_context_objects_lifecycle_state` performance index.

## 3. Seed the Knowledge Graph

The graph is loaded in two passes. Each is idempotent — safe to re-run.

### Pass 1: Load the 25 capability nodes (skills, concepts, projects)

```bash
# Docker
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/expanded_seed

# Local
python -m capability_commons.cli.seed --data-dir expanded_seed
```

Expected output:
```
Seed complete: 25 objects created, 0 skipped, 50 prerequisite edges (from YAML), 27 CSV edges created, 0 CSV edges skipped (duplicates)
```

### Pass 2: Load the 24 curriculum nodes (modules + assessments)

```bash
# Docker
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/capability_commons_module_seed_pack_v1

# Local
python -m capability_commons.cli.seed --data-dir capability_commons_module_seed_pack_v1
```

Expected output:
```
Seed complete: 24 objects created, 0 skipped, 0 prerequisite edges (from YAML), 98 CSV edges created, 0 CSV edges skipped (duplicates)
```

### What gets loaded

| Pass | Objects | Edge Types | Total Edges |
|------|---------|------------|-------------|
| 1 (capability) | 25 (skill_guide, concept_note, project_blueprint) | PREREQUISITE_FOR, NEXT_STEP_FOR | 77 |
| 2 (curriculum) | 24 (module, assessment) | PREREQUISITE_FOR, CONTAINS, ASSESSED_BY, VALIDATED_BY, NEXT_STEP_FOR | 98 |
| **Total** | **49** | **5 types** | **175** |

All objects are created in `PUBLISHED` state with `PUBLIC` visibility, so they appear immediately in the public API.

## 4. Verify the Backend

```bash
# Health check
curl http://localhost:8100/health

# List all published objects (should return 49)
curl http://localhost:8100/v1/public/objects | python -m json.tool | head -5

# Get the graph (nodes + edges for D3)
curl http://localhost:8100/v1/public/graph | python -m json.tool | head -20

# Get a specific object
curl http://localhost:8100/v1/public/objects/module.01-truth-tools-and-ai | python -m json.tool

# Search
curl -X POST http://localhost:8100/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "water storage"}' | python -m json.tool
```

## 5. Start the Frontend

```bash
cd ~/Projects/CapabilityCommonsSite

# Install dependencies
npm install

# Create .env if it doesn't exist
echo "PUBLIC_API_URL=http://localhost:8100" > .env

# Start dev server
npm run dev
```

The site starts at `http://localhost:4321`.

## 6. Verify the Full Stack

Open these pages to verify data flows end-to-end:

| URL | What to check |
|-----|---------------|
| `http://localhost:4321/` | Landing page loads, stats strip shows object count |
| `http://localhost:4321/explore` | Graph explorer shows 49 nodes with edges |
| `http://localhost:4321/explore/module.01-truth-tools-and-ai` | Module detail page with structured data, facets |
| `http://localhost:4321/explore/foundation.verify-and-cite` | Skill guide with prerequisites and next steps |
| `http://localhost:4321/search` | Search returns results from the live API |
| `http://localhost:4321/domains` | Domain grid links to filtered views |
| `http://localhost:4321/syllabus` | 12-week timeline shows curriculum modules |
| `http://localhost:4321/ask` | AI tutor sends retrieval requests to the backend |

## 7. Frontend Alignment Notes

The site's `ObjectType` union in `src/lib/types.ts` currently only includes `concept_note | skill_guide | project_blueprint`. With the curriculum seed loaded, the graph will also return `module` and `assessment` type objects. The site handles this gracefully because:

- `GraphNode.type` and `PublicObjectResponse.type` are typed as `string`, not a strict union
- The D3 graph explorer colors unknown types with a default gray
- Object detail pages render any type's `structured_data` as key-value pairs

To fully style the new types, you may want to:

1. **Update `ObjectType`** in `types.ts` to include `'module' | 'assessment'`
2. **Add color mappings** in `GraphExplorer.tsx` for module (e.g., purple) and assessment (e.g., orange)
3. **Update `StatsStrip.astro`** to reflect the new counts (49 objects, 175 edges)
4. **Add structured payload rendering** for module-specific fields (week, learning objectives, delivery profile) in `StructuredPayload.astro`

These are cosmetic enhancements — the site works with live data as-is.

## Troubleshooting

**Backend returns empty arrays:**
- Check that migrations ran: `alembic current` should show the latest revision
- Check that seed ran: `curl http://localhost:8100/v1/public/objects` should return 49 objects
- Check CORS: `.env` should have `CORS_ORIGINS=["http://localhost:4321"]`

**Site falls back to mock data:**
- Check `PUBLIC_API_URL` in `~/Projects/CapabilityCommonsSite/.env`
- Check backend is running: `curl http://localhost:8100/health`
- Check browser console for CORS errors

**Seed says "0 objects created, 49 skipped":**
- This is normal on re-run — seed is idempotent. The graph is already loaded.

**Docker Compose port conflict:**
- The DB maps to host port `5433` (not `5432`) to avoid conflicts with local Postgres
- The API runs on port `8100`
- If these conflict, edit `docker-compose.yml` port mappings

## Production Deployment

For production, you'll want to:

1. **Backend**: Push the Docker image to a registry and deploy to your hosting platform. Set `AUTH_ENABLED=true` and configure API keys via the CLI (`python -m capability_commons.cli.keys create --name prod-site`).

2. **Frontend**: Build the static site with `npm run build` and deploy the `dist/` directory to any static host (Cloudflare Pages, Vercel, Netlify). Set `PUBLIC_API_URL` to your production API URL at build time.

3. **Worker**: Run the outbox worker alongside the API for search indexing and embedding generation:
   ```bash
   python -m capability_commons.cli.worker
   ```
