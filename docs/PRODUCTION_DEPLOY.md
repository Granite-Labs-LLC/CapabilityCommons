# Production Deployment — Linux Server

This guide deploys the CapabilityCommons backend (FastAPI + Postgres 16 + pgvector) on a dedicated Linux machine, with the frontend (CapabilityCommonsSite) deployed separately on Replit or another static host.

## Prerequisites

- Ubuntu 22.04+ or Debian 12+ (any Linux with Docker works)
- Docker Engine 24+ and Docker Compose v2 (`docker compose` subcommand)
- At least 2 GB RAM, 10 GB disk
- A domain name pointed to the server (recommended for SSL)
- Firewall access to ports 22, 80, 443

## Quick Deploy

The repo now includes everything needed for a self-contained deployment:

```bash
# 1. Clone and configure
git clone --recurse-submodules https://github.com/Granite-Labs-LLC/CapabilityCommons.git
cd CapabilityCommons
cp .env.production .env
# Edit .env: set POSTGRES_PASSWORD, DOMAIN, CORS_ORIGINS, OPENAI_API_KEY, SENTRY_DSN

# 2. Start all services (API + Postgres + Caddy + backup)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Run migrations and seed
docker compose exec api alembic upgrade head
docker compose exec api python -m capability_commons.cli.seed --data-dir /app/expanded_seed
docker compose exec api python -m capability_commons.cli.seed --data-dir /app/capability_commons_module_seed_pack_v1

# 4. Create an API key for the frontend
docker compose exec api python -m capability_commons.cli.keys create \
  --workspace capability-commons --name prod-site

# 5. Verify
curl https://your-domain.com/health
```

Caddy automatically provisions TLS certificates. Backups run daily and retain 14 days.

For CD: pushes to `main` auto-deploy to staging via GitHub Actions. Production promotes via manual workflow dispatch. See `.github/workflows/deploy.yml`.

---

## Detailed Guide

## 1. Server Setup

```bash
# Create a deploy user (optional but recommended)
sudo adduser deploy
sudo usermod -aG docker deploy
su - deploy

# Clone the repo (with frontend submodule)
git clone --recurse-submodules https://github.com/Granite-Labs-LLC/CapabilityCommons.git
cd CapabilityCommons

# Install Docker if not present
# See https://docs.docker.com/engine/install/ubuntu/
```

## 2. Configure Environment

```bash
cp .env.production .env
# Edit .env: set POSTGRES_PASSWORD, DOMAIN, CORS_ORIGINS, and any API keys
```

The `.env.production` template has all settings documented with production-appropriate defaults. At minimum, change all `CHANGE_ME` values.

Generate an API key for the frontend (if auth is enabled):

```bash
docker compose exec api python -m capability_commons.cli.keys create --name prod-site
# Save the key — it's shown only once
```

## 3. Docker Compose Production Override

The repo includes `docker-compose.prod.yml` which adds:
- **Caddy** reverse proxy with auto-TLS (ports 80/443)
- **Backup** container running pg_dump daily with 14-day retention
- Memory limits and restart policies
- API port restricted to `127.0.0.1` (not publicly exposed)

No manual editing needed — it reads from `.env` for `POSTGRES_PASSWORD` and `DOMAIN`.

## 4. Start Services

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Wait for healthy status:

```bash
docker compose ps
# Both db and api should show "healthy"
```

## 5. Run Migrations and Seed

```bash
# Apply all database migrations
docker compose exec api alembic upgrade head

# Seed pass 1: 25 capability nodes
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/expanded_seed

# Seed pass 2: 24 curriculum nodes (12 modules + 12 assessments)
docker compose exec api python -m capability_commons.cli.seed \
  --data-dir /app/capability_commons_module_seed_pack_v1
```

Expected output:
```
Seed complete: 25 objects created, 0 skipped, 50 prerequisite edges (from YAML), 27 CSV edges created, 0 CSV edges skipped (duplicates)
Seed complete: 24 objects created, 0 skipped, 0 prerequisite edges (from YAML), 98 CSV edges created, 0 CSV edges skipped (duplicates)
```

## 6. Reverse Proxy (Caddy — included in Docker Compose)

Caddy runs as a Docker service in `docker-compose.prod.yml` and automatically provisions TLS certificates via Let's Encrypt. No separate installation needed.

Set the `DOMAIN` variable in your `.env` to your public domain:

```bash
DOMAIN=api.capabilitycommons.org
```

The Caddyfile is at `deploy/Caddyfile`. When `DOMAIN` is set, Caddy serves HTTPS automatically.

## 7. Firewall

```bash
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP (Caddy redirect)
sudo ufw allow 443/tcp    # HTTPS (Caddy)
# Do NOT expose 8100 — only the reverse proxy should reach it
sudo ufw enable
```

## 8. Verify

```bash
# Health check
curl https://api.capabilitycommons.org/health
# → {"status":"ok"}

# Object count (should return 49 objects)
curl https://api.capabilitycommons.org/v1/public/objects | python3 -c \
  "import sys, json; print(f'{len(json.load(sys.stdin))} objects')"

# Graph endpoint
curl https://api.capabilitycommons.org/v1/public/graph | python3 -c \
  "import sys, json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')"
```

## 9. Backups

### Automated (via Docker)

The `backup` service in `docker-compose.prod.yml` runs `pg_dump` every 24 hours and retains 14 days of backups in a Docker volume.

```bash
# Check backup logs
docker compose logs backup --tail=5
```

### Manual backup and restore

Scripts are included in `deploy/`:

```bash
# Backup
./deploy/backup.sh              # Saves to ./backups/
./deploy/backup.sh /path/to/dir  # Custom directory

# Restore
./deploy/restore.sh backups/cc_20260325_020000.sql.gz
```

## 10. Monitoring

### Logs

```bash
# Follow all logs
docker compose logs -f

# API logs only
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

### Health check for uptime monitoring

Point any uptime monitor (UptimeRobot, Healthchecks.io, etc.) at:

```
GET https://api.capabilitycommons.org/health
```

Expected response: `{"status":"ok"}` with HTTP 200.

### Disk space

```bash
# Check pgdata volume size
docker system df -v | grep pgdata

# Overall disk usage
df -h /
```

## 11. Updating

```bash
cd /home/deploy/CapabilityCommons
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run any new migrations
docker compose exec api alembic upgrade head
```

## 12. Connecting the Frontend

The CapabilityCommonsSite (Astro static site) is included as a git submodule at `apps/site/`. It connects to this API at build time and at runtime.

**Build time:** Astro fetches all objects and graph data to generate static pages.

**Runtime:** React islands (search, graph explorer, guided ask, feedback) make client-side API calls.

This means the API must be accessible:
1. From the build environment (build time)
2. From users' browsers (runtime)

**Building the frontend:**

```bash
cd apps/site
npm install
PUBLIC_API_URL=https://api.capabilitycommons.org npm run build
# Static output in apps/site/dist/ — deploy to any static host
```

On the frontend host, set the environment variable:

```bash
PUBLIC_API_URL=https://api.capabilitycommons.org
```

### CORS checklist

Ensure your production `.env` includes the frontend URL:

```bash
CORS_ORIGINS=["https://your-site.replit.app"]
```

If you add a custom domain to the frontend, add it too:

```bash
CORS_ORIGINS=["https://your-site.replit.app","https://capabilitycommons.org"]
```

Restart the API after changing CORS settings:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
```
