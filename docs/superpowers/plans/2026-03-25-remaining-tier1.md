# Remaining Tier 1: Production Deployment Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining Tier 1 production items so the system can be deployed to a VPS with automated CI/CD, HTTPS, backups, and a documented first ingestion run.

**Architecture:** VPS deployment with Docker Compose. Caddy runs as a Docker service alongside the API and Postgres for a fully self-contained stack. GitHub Actions CD deploys via SSH on merge to main. Backups use pg_dump on a cron schedule inside a dedicated container. Environment-specific config via `.env.staging` and `.env.production` templates.

**Tech Stack:** GitHub Actions (CD), Docker Compose, Caddy (auto-TLS reverse proxy), pg_dump, SSH deploy

---

## File Structure

### New files
- `.github/workflows/deploy.yml` — CD workflow (SSH deploy to staging/production)
- `deploy/Caddyfile` — Caddy reverse proxy config with auto-TLS
- `deploy/backup.sh` — pg_dump backup script with retention
- `deploy/restore.sh` — Database restore from backup
- `docker-compose.prod.yml` — Production compose override (Caddy, restart policies, memory limits)
- `.env.staging` — Staging environment template
- `.env.production` — Production environment template

### Modified files
- `src/capability_commons/config.py` — Adjust rate limit defaults for production
- `docker-compose.yml` — Add backup service definition
- `docs/PRODUCTION_DEPLOY.md` — Update to reference new files
- `TODO.md` — Mark items complete
- `STATUS.md` — Update deployment section

---

## Chunk 1: Deployment Infrastructure

### Task 1: Production Docker Compose with Caddy

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `deploy/Caddyfile`

- [ ] **Step 1: Create the deploy directory**

```bash
mkdir -p deploy
```

- [ ] **Step 2: Create the Caddyfile**

Create `deploy/Caddyfile`:

```
{$DOMAIN:localhost} {
    reverse_proxy api:8100
}
```

This uses an environment variable `DOMAIN` so the same Caddyfile works for staging and production. When `DOMAIN` is unset, it defaults to `localhost` (no TLS) for local testing.

- [ ] **Step 3: Create docker-compose.prod.yml**

Create `docker-compose.prod.yml`:

```yaml
# Production overrides — use with:
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
services:
  db:
    restart: always
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
    deploy:
      resources:
        limits:
          memory: 1G

  api:
    restart: always
    ports: !override
      - "127.0.0.1:8100:8100"
    env_file: .env
    deploy:
      resources:
        limits:
          memory: 512M

  caddy:
    image: caddy:2-alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    environment:
      DOMAIN: ${DOMAIN:-localhost}
    depends_on:
      api:
        condition: service_healthy

  backup:
    image: pgvector/pgvector:pg16
    entrypoint: /bin/sh
    command: >
      -c 'while true; do
        TIMESTAMP=$$(date +%Y%m%d_%H%M%S);
        pg_dump -h db -U postgres capability_commons | gzip > /backups/cc_$$TIMESTAMP.sql.gz;
        find /backups -name "cc_*.sql.gz" -mtime +14 -delete;
        echo "[$$TIMESTAMP] Backup complete";
        sleep 86400;
      done'
    environment:
      PGPASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
    volumes:
      - backups:/backups
    depends_on:
      db:
        condition: service_healthy

volumes:
  caddy_data:
  caddy_config:
  backups:
```

Key decisions:
- API port bound to `127.0.0.1` only (not exposed publicly — Caddy handles external traffic)
- Caddy auto-provisions TLS via Let's Encrypt when `DOMAIN` is a real domain
- Backup container runs pg_dump every 24 hours and retains 14 days
- `POSTGRES_PASSWORD` is required (fails fast if unset)

- [ ] **Step 4: Verify the compose files are valid**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
```
Expected: No errors (valid merged config). Note: this may warn about `!override` — that's fine, it's a compose v2 feature.

- [ ] **Step 5: Commit**

```bash
git add deploy/Caddyfile docker-compose.prod.yml
git commit -m "feat: add production Docker Compose with Caddy TLS and automated backups"
```

---

### Task 2: Backup and Restore Scripts

**Files:**
- Create: `deploy/backup.sh`
- Create: `deploy/restore.sh`

- [ ] **Step 1: Create the backup script**

Create `deploy/backup.sh`:

```bash
#!/usr/bin/env bash
# Manual backup script — run from the project root.
# Usage: ./deploy/backup.sh [backup_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$BACKUP_DIR/cc_$TIMESTAMP.sql.gz"

docker compose exec -T db pg_dump -U postgres capability_commons | gzip > "$OUTFILE"

echo "Backup saved: $OUTFILE ($(du -h "$OUTFILE" | cut -f1))"

# Prune backups older than 14 days
find "$BACKUP_DIR" -name "cc_*.sql.gz" -mtime +14 -delete
```

- [ ] **Step 2: Create the restore script**

Create `deploy/restore.sh`:

```bash
#!/usr/bin/env bash
# Restore a database backup.
# Usage: ./deploy/restore.sh <backup_file>
# Example: ./deploy/restore.sh backups/cc_20260325_020000.sql.gz
set -euo pipefail

BACKUP_FILE="${1:?Usage: $0 <backup_file.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: File not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will drop and recreate the capability_commons database."
echo "Press Ctrl-C to cancel, or Enter to continue."
read -r

# Drop and recreate database
docker compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS capability_commons;"
docker compose exec -T db psql -U postgres -c "CREATE DATABASE capability_commons;"

# Restore
gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U postgres capability_commons

echo "Restore complete from: $BACKUP_FILE"
echo "Run 'docker compose exec api alembic upgrade head' if migrations are newer than the backup."
```

- [ ] **Step 3: Make scripts executable**

```bash
chmod +x deploy/backup.sh deploy/restore.sh
```

- [ ] **Step 4: Commit**

```bash
git add deploy/backup.sh deploy/restore.sh
git commit -m "feat: add backup and restore scripts for pg_dump workflow"
```

---

### Task 3: Environment Templates

**Files:**
- Create: `.env.staging`
- Create: `.env.production`

- [ ] **Step 1: Create .env.staging**

Create `.env.staging`:

```bash
# Staging environment — copy to .env on staging server
APP_ENV=staging
APP_NAME=Capability Commons API (Staging)

# Database — use the Docker internal hostname
DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_ME@db:5432/capability_commons
POSTGRES_PASSWORD=CHANGE_ME

# Connection pool — smaller for staging
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true

# CORS — set to your staging frontend URL
CORS_ORIGINS=["https://staging.capabilitycommons.org"]

# Auth
AUTH_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PUBLIC_PER_MINUTE=200

# Embeddings — optional for staging
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small

# Observability
SENTRY_DSN=
METRICS_ENABLED=true

# Deployment
DOMAIN=staging-api.capabilitycommons.org
```

- [ ] **Step 2: Create .env.production**

Create `.env.production`:

```bash
# Production environment — copy to .env on production server
APP_ENV=production
APP_NAME=Capability Commons API

# Database — use strong password, set via GitHub secret
DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_ME@db:5432/capability_commons
POSTGRES_PASSWORD=CHANGE_ME

# Connection pool — tuned for production
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=3600
DB_POOL_PRE_PING=true

# CORS — restrict to production frontend domain(s)
CORS_ORIGINS=["https://capabilitycommons.org"]

# Auth
AUTH_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PUBLIC_PER_MINUTE=200

# Embeddings
OPENAI_API_KEY=CHANGE_ME
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BATCH_SIZE=50

# Observability
SENTRY_DSN=CHANGE_ME
METRICS_ENABLED=true

# Deployment
DOMAIN=api.capabilitycommons.org
```

- [ ] **Step 3: Add to .gitignore safeguard**

Verify `.env` is in `.gitignore` (it should already be — `.env.staging` and `.env.production` are templates with placeholder values, so they're safe to commit).

```bash
grep -q "^\.env$" .gitignore && echo "OK: .env is gitignored" || echo "WARNING: add .env to .gitignore"
```

- [ ] **Step 4: Commit**

```bash
git add .env.staging .env.production
git commit -m "feat: add staging and production environment templates"
```

---

## Chunk 2: CD Pipeline and Rate Limits

### Task 4: GitHub Actions CD Workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

The CD workflow:
- Triggers on push to `main` (after CI passes)
- Builds Docker image on the server via SSH
- Runs migrations
- Restarts services
- Manual dispatch for production promotion

- [ ] **Step 1: Create the deploy workflow**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: "Deploy target"
        required: true
        default: "staging"
        type: choice
        options:
          - staging
          - production

concurrency:
  group: deploy-${{ github.event.inputs.environment || 'staging' }}
  cancel-in-progress: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'staging' }}
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd ${{ secrets.DEPLOY_PATH }}
            git pull origin main
            docker compose -f docker-compose.yml -f docker-compose.prod.yml build api
            docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            docker compose exec -T api alembic upgrade head
            echo "Deploy complete at $(date)"

      - name: Verify health
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            sleep 5
            curl -sf http://localhost:8100/health || (echo "Health check failed!" && exit 1)
            echo "Health check passed"
```

**Required GitHub secrets** (set per environment in repo Settings → Environments):

| Secret | Description | Example |
|--------|-------------|---------|
| `DEPLOY_HOST` | Server IP or hostname | `203.0.113.42` |
| `DEPLOY_USER` | SSH user on server | `deploy` |
| `DEPLOY_SSH_KEY` | Private SSH key for deploy user | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DEPLOY_PATH` | Path to repo on server | `/home/deploy/CapabilityCommons` |

**Setup instructions** (on the VPS):

```bash
# Create deploy user (if not already done)
sudo adduser deploy
sudo usermod -aG docker deploy

# Generate SSH key pair for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys

# Copy the PRIVATE key content to GitHub secret DEPLOY_SSH_KEY
cat ~/.ssh/github_deploy
```

- [ ] **Step 2: Verify YAML validity**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
```
Expected: No error.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add GitHub Actions CD workflow (SSH deploy to staging/production)"
```

---

### Task 5: Rate Limit Tuning

**Files:**
- Modify: `src/capability_commons/config.py`

The current defaults are `100` per-key and `300` public per minute. For production with a small user base, tighter public limits prevent abuse while authenticated users get generous allowances.

- [ ] **Step 1: Review current rate limits**

Current values in `src/capability_commons/config.py`:
```python
rate_limit_per_minute: int = 100
rate_limit_public_per_minute: int = 300
```

Decision: Keep authenticated at 100 (generous for API consumers). Lower public from 300 to 60 (1 req/sec average — adequate for browsing, prevents scraping). These are overridable via env vars.

- [ ] **Step 2: Update defaults**

In `src/capability_commons/config.py`, change:

```python
    rate_limit_public_per_minute: int = 300
```

to:

```python
    rate_limit_public_per_minute: int = 60
```

- [ ] **Step 3: Update .env.example**

Change the rate limit comment section in `.env.example`:

```bash
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PUBLIC_PER_MINUTE=60
```

- [ ] **Step 4: Run tests to verify nothing breaks**

```bash
.venv/bin/python -m pytest tests/test_rate_limit.py -v
```
Expected: All pass (tests should use the config value, not hardcode 300).

- [ ] **Step 5: Commit**

```bash
git add src/capability_commons/config.py .env.example
git commit -m "feat: tune rate limits (public 300→60/min, authenticated stays at 100/min)"
```

---

## Chunk 3: Documentation and Completion

### Task 6: Update Production Deploy Docs

**Files:**
- Modify: `docs/PRODUCTION_DEPLOY.md`
- Modify: `docs/DEPLOY_CHECKLIST.md`

- [ ] **Step 1: Update PRODUCTION_DEPLOY.md**

Add a new section at the top (after § 1) describing the simplified deployment with the new files:

```markdown
## Quick Deploy (New Method)

The repo now includes everything needed for a self-contained deployment:

```bash
# 1. Clone and configure
git clone https://github.com/Granite-Labs-LLC/CapabilityCommons.git
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
```

- [ ] **Step 2: Update DEPLOY_CHECKLIST.md**

Update Phase 1 items to reference the new `docker-compose.prod.yml` and `deploy/` scripts. Replace the manual Caddy installation steps with:

```markdown
- [ ] **1.3** Start all services (Caddy is included in the compose stack)
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  ```
```

And update the backup step to reference the backup container:

```markdown
- [ ] **1.11** Verify backups are running
  ```bash
  docker compose logs backup --tail=5
  # Should show daily backup entries
  ```
  For manual backup: `./deploy/backup.sh`
  For restore: `./deploy/restore.sh backups/cc_YYYYMMDD_HHMMSS.sql.gz`
```

- [ ] **Step 3: Commit**

```bash
git add docs/PRODUCTION_DEPLOY.md docs/DEPLOY_CHECKLIST.md
git commit -m "docs: update deploy guides with new compose stack and CD pipeline"
```

---

### Task 7: Update TODO.md and STATUS.md

**Files:**
- Modify: `TODO.md`
- Modify: `STATUS.md`

- [ ] **Step 1: Mark completed items in TODO.md**

Mark these items as done:
- [x] Deploy pipeline (staging auto-deploy, manual production)
- [x] Separate staging and production configs
- [x] HTTPS enforcement (Caddy in Docker)
- [x] Backup strategy (automated daily + manual scripts)
- [x] Rate limit tuning

Update the "Quick reference" section to reflect progress.

- [ ] **Step 2: Update STATUS.md deployment section**

Update the Deployment table:

```markdown
| Component | Status |
|-----------|--------|
| Dockerfile | Production-ready (slim Python 3.14 image, port 8100) |
| docker-compose.yml | Development (pgvector + API) |
| docker-compose.prod.yml | Production (+ Caddy TLS + backup container) |
| `.env.staging` / `.env.production` | Templates provided |
| Alembic migrations | 5 applied, auto-generate works |
| GitHub Actions CI | Configured (lint, typecheck, test, integration, Docker build) |
| GitHub Actions CD | Configured (SSH deploy to staging, manual promote to production) |
| Caddy reverse proxy | In Docker Compose (auto-TLS via Let's Encrypt) |
| Backup/restore | Automated daily + manual scripts in deploy/ |
```

- [ ] **Step 3: Commit**

```bash
git add TODO.md STATUS.md
git commit -m "docs: mark remaining Tier 1 items complete, update status"
```

---

## Summary

After completing all 7 tasks, the deployment infrastructure delivers:

| Item | Before | After |
|------|--------|-------|
| **CD pipeline** | None | GitHub Actions: auto-deploy staging on merge, manual production |
| **Env config** | Single `.env.example` | `.env.staging` + `.env.production` templates |
| **HTTPS** | Manual Caddy install documented | Caddy in Docker Compose (auto-TLS) |
| **Backups** | Documented but no tracked scripts | Automated container + manual backup/restore scripts |
| **Rate limits** | 300 public/min | 60 public/min (tuned for launch) |
| **Deploy docs** | Manual multi-step guide | Simplified 5-command quick deploy |

**Remaining Tier 1 items after this plan** (not automatable):
- First real ingestion run (manual: pick a PDF, run the 8-pass pipeline, review output)
- Safety review for high-risk content (manual editorial process)
